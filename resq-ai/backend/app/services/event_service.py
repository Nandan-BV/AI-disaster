from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_SetSRID, ST_MakePoint
from geoalchemy2.shape import to_shape

from app.models.event import Event
from app.schemas.event import EventCreate


class EventService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_event(self, event_data: EventCreate) -> Event:
        point = ST_SetSRID(ST_MakePoint(event_data.longitude, event_data.latitude), 4326)
        
        event = Event(
            source=event_data.source,
            text_content=event_data.text_content,
            event_type=event_data.event_type,
            latitude=event_data.latitude,
            longitude=event_data.longitude,
            location=point,
            location_name=event_data.location_name,
            timestamp=event_data.timestamp,
            image_url=event_data.image_url,
            video_url=event_data.video_url,
            metadata=event_data.metadata or {},
        )
        
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def get_event_by_id(self, event_id: UUID) -> Optional[Event]:
        result = await self.db.execute(
            select(Event).where(Event.id == event_id)
        )
        return result.scalar_one_or_none()

    async def get_events(
        self,
        source: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Event], int]:
        query = select(Event)
        
        if source:
            query = query.where(Event.source == source)
        if start_date:
            query = query.where(Event.timestamp >= start_date)
        if end_date:
            query = query.where(Event.timestamp <= end_date)
        
        query = query.order_by(Event.timestamp.desc())
        
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()
        
        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        events = list(result.scalars().all())
        
        return events, total

    async def delete_event(self, event_id: UUID) -> bool:
        event = await self.get_event_by_id(event_id)
        if not event:
            return False
        
        await self.db.delete(event)
        await self.db.commit()
        return True