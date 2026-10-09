#!/usr/bin/env python3
"""
Script to load sample environmental conditions into the database.
Run this after starting the PostgreSQL database and running migrations.
Note: This requires incidents to already exist in the database.
The incident_id_placeholder values need to be replaced with actual incident UUIDs.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from app.config import settings
from app.models.incident import Incident
from app.models.risk import EnvironmentalConditions
from app.database import Base


async def load_environmental_conditions():
    sample_file = Path(__file__).parent / "environmental_conditions.json"
    
    if not sample_file.exists():
        print(f"Error: Sample file not found at {sample_file}")
        sys.exit(1)
    
    with open(sample_file, "r") as f:
        conditions_data = json.load(f)
    
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as session:
        # Get all incidents to map placeholder IDs
        result = await session.execute(select(Incident).order_by(Incident.created_at))
        incidents = list(result.scalars().all())
        
        if not incidents:
            print("No incidents found in database. Please create incidents first.")
            print("Run: python load_sample_events.py")
            print("Then: python data/process_events.py")
            await engine.dispose()
            return
        
        print(f"Found {len(incidents)} incidents")
        
        # Map placeholder IDs to actual incident IDs
        # This is a simple mapping for demo - in practice you'd match by some criteria
        for i, condition_data in enumerate(conditions_data):
            if i < len(incidents):
                incident_id = incidents[i].id
            else:
                incident_id = incidents[0].id  # Fallback to first incident
            
            # Check if already exists for this incident and timestamp
            from sqlalchemy import select
            existing = await session.execute(
                select(EnvironmentalConditions)
                .where(
                    EnvironmentalConditions.incident_id == incident_id,
                    EnvironmentalConditions.timestamp == datetime.fromisoformat(condition_data["timestamp"])
                )
            )
            if existing.scalar_one_or_none():
                print(f"Condition for incident {incident_id} at {condition_data['timestamp']} already exists, skipping")
                continue
            
            condition = EnvironmentalConditions(
                id=uuid4(),
                incident_id=incident_id,
                timestamp=datetime.fromisoformat(condition_data["timestamp"]),
                temperature=condition_data.get("temperature"),
                rainfall=condition_data.get("rainfall"),
                wind_speed=condition_data.get("wind_speed"),
                humidity=condition_data.get("humidity"),
                water_level=condition_data.get("water_level"),
                visibility=condition_data.get("visibility"),
                weather_description=condition_data.get("weather_description"),
                metadata=condition_data.get("metadata", {}),
            )
            
            session.add(condition)
            print(f"Added environmental condition for incident {incident_id} at {condition_data['timestamp']}")
        
        await session.commit()
        print(f"\nSuccessfully loaded {len(conditions_data)} environmental conditions!")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(load_environmental_conditions())