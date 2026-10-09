from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Text, DateTime, Float, JSON, ForeignKey, Index, Integer, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum

from app.database import Base


class IncidentStatus(str, enum.Enum):
    EMERGING = "emerging"
    ACTIVE = "active"
    RESOLVED = "resolved"


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_type = Column(String(50), nullable=True, index=True)
    title = Column(String(500), nullable=False)
    summary = Column(Text, nullable=True)
    centroid_latitude = Column(Float, nullable=True)
    centroid_longitude = Column(Float, nullable=True)
    start_time = Column(DateTime, nullable=False, index=True)
    last_updated = Column(DateTime, nullable=False, index=True)
    event_count = Column(Integer, default=1, nullable=False)
    status = Column(SQLEnum(IncidentStatus), default=IncidentStatus.EMERGING, nullable=False, index=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    events = relationship("IncidentEvent", back_populates="incident", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_incidents_status_type", "status", "incident_type"),
        Index("ix_incidents_time_range", "start_time", "last_updated"),
    )

    def __repr__(self):
        return f"<Incident(id={self.id}, type={self.incident_type}, title={self.title[:50]}, events={self.event_count})>"


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    similarity_score = Column(Float, nullable=True)
    geographic_distance_meters = Column(Float, nullable=True)
    temporal_distance_minutes = Column(Float, nullable=True)
    disaster_type_match = Column(JSON, nullable=True)  # {"event_type": "flood", "incident_type": "flood"}
    assignment_confidence = Column(Float, nullable=True)
    relationship_components = Column(JSON, nullable=True)  # Detailed breakdown
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    incident = relationship("Incident", back_populates="events")

    __table_args__ = (
        Index("ix_incident_events_incident_event", "incident_id", "event_id", unique=True),
    )

    def __repr__(self):
        return f"<IncidentEvent(incident={self.incident_id}, event={self.event_id}, score={self.similarity_score})>"