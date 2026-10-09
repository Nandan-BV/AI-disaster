#!/usr/bin/env python3
"""
Script to load sample population zones into the database.
Run this after starting the PostgreSQL database and running migrations.
"""

import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from geoalchemy2.functions import ST_SetSRID, ST_MakePoint

from app.config import settings
from app.models.risk import PopulationZone
from app.database import Base


async def load_population_zones():
    sample_file = Path(__file__).parent / "population_zones.json"
    
    if not sample_file.exists():
        print(f"Error: Sample file not found at {sample_file}")
        sys.exit(1)
    
    with open(sample_file, "r") as f:
        zones_data = json.load(f)
    
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as session:
        for zone_data in zones_data:
            # Check if already exists (by name)
            from sqlalchemy import select
            existing = await session.execute(
                select(PopulationZone).where(PopulationZone.name == zone_data["name"])
            )
            if existing.scalar_one_or_none():
                print(f"Zone {zone_data['name']} already exists, skipping")
                continue
            
            point = ST_SetSRID(
                ST_MakePoint(zone_data["longitude"], zone_data["latitude"]), 4326
            )
            
            zone = PopulationZone(
                id=uuid4(),
                name=zone_data["name"],
                population=zone_data["population"],
                latitude=zone_data["latitude"],
                longitude=zone_data["longitude"],
                location=point,
                vulnerability_factor=zone_data.get("vulnerability_factor", 0.5),
                metadata=zone_data.get("metadata", {}),
            )
            
            session.add(zone)
            print(f"Added zone: {zone.name} (population: {zone.population})")
        
        await session.commit()
        print(f"\nSuccessfully loaded {len(zones_data)} population zones!")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(load_population_zones())