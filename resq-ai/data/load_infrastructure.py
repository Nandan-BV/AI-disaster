#!/usr/bin/env python3
"""
Script to load sample infrastructure into the database.
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
from app.models.infrastructure import Infrastructure, InfrastructureType, InfrastructureStatus, RoadStatus
from app.database import Base


async def load_sample_infrastructure():
    sample_file = Path(__file__).parent / "infrastructure.json"

    if not sample_file.exists():
        print(f"Error: Sample file not found at {sample_file}")
        sys.exit(1)

    with open(sample_file, "r") as f:
        infrastructure_data = json.load(f)

    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        for infra_data in infrastructure_data:
            # Check if already exists (by name)
            from sqlalchemy import select
            existing = await session.execute(
                select(Infrastructure).where(Infrastructure.name == infra_data["name"])
            )
            if existing.scalar_one_or_none():
                print(f"Skipping existing: {infra_data['name']}")
                continue

            point = ST_SetSRID(
                ST_MakePoint(infra_data["longitude"], infra_data["latitude"]), 4326
            )

            infra = Infrastructure(
                id=uuid4(),
                name=infra_data["name"],
                infrastructure_type=InfrastructureType(infra_data["infrastructure_type"]),
                latitude=infra_data["latitude"],
                longitude=infra_data["longitude"],
                location=point,
                address=infra_data.get("address"),
                capacity=infra_data.get("capacity"),
                status=InfrastructureStatus(infra_data.get("status", "operational")),
                road_status=RoadStatus(infra_data["road_status"]) if infra_data.get("road_status") else None,
                metadata=infra_data.get("metadata", {}),
            )

            session.add(infra)
            print(f"Added: {infra.name} ({infra.infrastructure_type.value}) at ({infra.latitude}, {infra.longitude})")

        await session.commit()
        print(f"\nSuccessfully loaded {len(infrastructure_data)} infrastructure records!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(load_sample_infrastructure())