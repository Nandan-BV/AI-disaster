#!/usr/bin/env python3
"""
Load test scenarios for incident clustering testing.

This creates events for the 4 test scenarios:
1. Same flood (4 events, same location, close time) - should cluster
2. Separate floods (2 events, different location) - should NOT cluster
3. Same location, different time (2 events, 6 days apart) - should NOT cluster
4. Different disaster types (2 events, flood + wildfire) - should NOT cluster
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from geoalchemy2.functions import ST_SetSRID, ST_MakePoint

from app.config import settings
from app.database import Base
from app.models.event import Event


async def load_test_scenarios():
    scenario_file = Path(__file__).parent / "test_scenarios.json"

    if not scenario_file.exists():
        print(f"Error: Scenario file not found at {scenario_file}")
        sys.exit(1)

    with open(scenario_file, "r") as f:
        events_data = json.load(f)

    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        for event_data in events_data:
            # Check if already exists
            event_id = UUID(event_data["id"])
            existing = await session.execute(select(Event).where(Event.id == event_id))
            if existing.scalar_one_or_none():
                print(f"Event {event_id} already exists, skipping")
                continue

            point = ST_SetSRID(
                ST_MakePoint(event_data["longitude"], event_data["latitude"]), 4326
            )

            event = Event(
                id=event_id,
                source=event_data["source"],
                text_content=event_data.get("text_content"),
                event_type=event_data.get("event_type"),
                latitude=event_data["latitude"],
                longitude=event_data["longitude"],
                location=point,
                location_name=event_data.get("location_name"),
                timestamp=datetime.fromisoformat(event_data["timestamp"]),
                image_url=event_data.get("image_url"),
                video_url=event_data.get("video_url"),
                metadata=event_data.get("metadata", {}),
            )

            session.add(event)
            print(f"Added event: {event.id} ({event_data['metadata'].get('scenario', 'unknown')})")

        await session.commit()
        print(f"\nSuccessfully loaded {len(events_data)} test scenario events!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(load_test_scenarios())