from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Text, DateTime, JSON, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class EventAIAnalysis(Base):
    __tablename__ = "event_ai_analysis"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    modality = Column(String(50), nullable=False)
    disaster_type = Column(String(50), nullable=True, index=True)
    disaster_type_confidence = Column(JSON, nullable=True)
    severity_indicators = Column(JSON, nullable=True, default=list)
    location_mentions = Column(JSON, nullable=True, default=list)
    damage_observed = Column(JSON, nullable=True, default=list)
    people_affected = Column(Text, nullable=True)
    vehicles_observed = Column(JSON, nullable=True, default=list)
    infrastructure_damage = Column(JSON, nullable=True, default=list)
    environmental_conditions = Column(JSON, nullable=True, default=list)
    summary = Column(Text, nullable=True)
    evidence_description = Column(Text, nullable=True)
    model_name = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    event = relationship("Event", backref="ai_analyses")

    __table_args__ = (
        Index("ix_event_ai_analysis_event_created", "event_id", "created_at"),
    )

    def __repr__(self):
        return f"<EventAIAnalysis(id={self.id}, event_id={self.event_id}, modality={self.modality}, disaster_type={self.disaster_type})>"