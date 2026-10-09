#!/usr/bin/env python3
"""
Script to load sample events into the database.
Run this after starting the PostgreSQL database and running migrations.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from geoalchemy2.functions import ST_SetSRID, ST_MakePoint

from app.config import settings
from app.models.event import Event
from app.database import Base


async def load_sample_events():
    sample_file = Path(__file__).parent / "sample_events.json"
    
    if not sample_file.exists():
        print(f"Error: Sample file not found at {sample_file}")
        sys.exit(1)
    
    with open(sample_file, "r") as f:
        events_data = json.load(f)
    
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as session:
        for event_data in events_data:
            point = ST_SetSRID(
                ST_MakePoint(event_data["longitude"], event_data["latitude"]), 4326
            )
            
            event = Event(
                id=uuid4(),
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
            print(f"Added event: {event.source} - {event.event_type} at {event.location_name}")
        
        await session.commit()
        print(f"\nSuccessfully loaded {len(events_data)} sample events!")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(load_sample_events())