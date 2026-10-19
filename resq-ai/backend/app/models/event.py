from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Text, DateTime, Float, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
import uuid

from app.database import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(100), nullable=False, index=True)
    external_id = Column(String(255), nullable=True)
    text_content = Column(Text, nullable=True)
    event_type = Column(String(50), nullable=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    location_name = Column(String(200), nullable=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    image_url = Column(String(500), nullable=True)
    video_url = Column(String(500), nullable=True)
    metadata = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("uq_events_source_external_id", "source", "external_id", unique=True),
        Index("ix_events_timestamp_desc", timestamp.desc()),
        Index("ix_events_location", "location", postgresql_using="gist"),
    )

    def __repr__(self):
        return f"<Event(id={self.id}, source={self.source}, lat={self.latitude}, lon={self.longitude})>"