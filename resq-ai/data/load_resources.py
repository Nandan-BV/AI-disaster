#!/usr/bin/env python3
"""
Script to load sample resources into the database.
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
from app.models.resource import Resource, ResourceType, ResourceStatus
from app.database import Base


async def load_sample_resources():
    sample_file = Path(__file__).parent / "resources.json"
    
    if not sample_file.exists():
        print(f"Error: Sample file not found at {sample_file}")
        sys.exit(1)
    
    with open(sample_file, "r") as f:
        resources_data = json.load(f)
    
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as session:
        for resource_data in resources_data:
            # Check if already exists (by name)
            from sqlalchemy import select
            existing = await session.execute(
                select(Resource).where(Resource.name == resource_data["name"])
            )
            if existing.scalar_one_or_none():
                print(f"Resource {resource_data['name']} already exists, skipping")
                continue
            
            point = ST_SetSRID(
                ST_MakePoint(resource_data["longitude"], resource_data["latitude"]), 4326
            )
            
            resource = Resource(
                id=uuid4(),
                name=resource_data["name"],
                resource_type=ResourceType(resource_data["resource_type"]),
                status=ResourceStatus(resource_data.get("status", "available")),
                latitude=resource_data["latitude"],
                longitude=resource_data["longitude"],
                location=point,
                address=resource_data.get("address"),
                capacity=resource_data.get("capacity"),
                current_load=resource_data.get("current_load", 0),
                capabilities=resource_data.get("capabilities", {}),
                organization=resource_data.get("organization"),
                metadata=resource_data.get("metadata", {}),
            )
            
            session.add(resource)
            print(f"Added resource: {resource.name} ({resource.resource_type.value}) at ({resource.latitude}, {resource.longitude})")
        
        await session.commit()
        print(f"\nSuccessfully loaded {len(resources_data)} sample resources!")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(load_sample_resources())