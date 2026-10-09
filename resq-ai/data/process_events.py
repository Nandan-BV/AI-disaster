#!/usr/bin/env python3
"""
Batch processing script for incident clustering.

Processes existing events from Phase 1/2 and assigns them to incidents.

Usage:
    python data/process_events.py [--event-ids ID1 ID2 ...] [--limit N] [--dry-run]
"""

import asyncio
import argparse
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from app.config import settings
from app.database import Base
from app.models.event import Event
from app.models.incident import Incident, IncidentEvent
from ai.services.clustering_service import process_events_batch


async def run_batch_process(
    event_ids: list[UUID] = None,
    limit: int = None,
    dry_run: bool = False,
):
    """Run the batch processing."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        print(f"Starting batch processing...")
        if event_ids:
            print(f"Processing specific events: {[str(e) for e in event_ids]}")
        elif limit:
            print(f"Processing up to {limit} events")
        else:
            print("Processing all unprocessed events")

        if dry_run:
            print("DRY RUN MODE - No changes will be committed")
            # In dry run, we'd need to wrap in transaction and rollback
            # For simplicity, just show what would be processed
            query = select(Event).order_by(Event.timestamp)
            if event_ids:
                query = query.where(Event.id.in_(event_ids))
            elif limit:
                query = query.limit(limit)

            result = await session.execute(query)
            events = list(result.scalars().all())

            print(f"\nWould process {len(events)} events:")
            for event in events:
                existing = await session.execute(
                    select(IncidentEvent).where(IncidentEvent.event_id == event.id)
                )
                if existing.scalar_one_or_none():
                    print(f"  {event.id}: Already assigned to incident")
                else:
                    print(f"  {event.id}: {event.text_content[:80] if event.text_content else 'No text'}...")

            await engine.dispose()
            return

        # Run actual processing
        result = await process_events_batch(session, event_ids=event_ids, limit=limit)

        print(f"\nProcessing complete!")
        print(f"  Events processed: {result['processed_events']}")
        print(f"  New incidents created: {result['new_incidents']}")
        print(f"  Existing incidents updated: {result['updated_incidents']}")

        if result['errors']:
            print(f"  Errors: {len(result['errors'])}")
            for error in result['errors']:
                print(f"    Event {error['event_id']}: {error['error']}")

        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Batch process events for incident clustering")
    parser.add_argument(
        "--event-ids",
        nargs="+",
        help="Specific event UUIDs to process",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of events to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without making changes",
    )

    args = parser.parse_args()

    event_ids = None
    if args.event_ids:
        try:
            event_ids = [UUID(eid) for eid in args.event_ids]
        except ValueError as e:
            print(f"Error: Invalid UUID format: {e}")
            sys.exit(1)

    asyncio.run(run_batch_process(
        event_ids=event_ids,
        limit=args.limit,
        dry_run=args.dry_run,
    ))


if __name__ == "__main__":
    main()