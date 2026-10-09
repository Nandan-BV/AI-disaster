from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Text, DateTime, Float, JSON, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum

from app.database import Base


class EvidenceType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    GEOGRAPHIC = "geographic"
    TEMPORAL = "temporal"
    MULTIMODAL = "multimodal"
    CONSISTENCY = "consistency"
    SOURCE_DIVERSITY = "source_diversity"


class EvidenceRole(str, enum.Enum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    NEUTRAL = "neutral"
    UNCERTAIN = "uncertain"


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    evidence_type = Column(SQLEnum(EvidenceType), nullable=False, index=True)
    evidence_role = Column(SQLEnum(EvidenceRole), nullable=False, index=True)
    description = Column(Text, nullable=False)
    evidence_quality = Column(Float, nullable=True)  # 0-1 quality score
    confidence = Column(Float, nullable=True)  # 0-1 confidence in this evidence
    source = Column(String(100), nullable=True)  # event source
    metadata = Column(JSON, nullable=True, default=dict)  # Additional details
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_evidence_incident_role", "incident_id", "evidence_role"),
        Index("ix_evidence_incident_type", "incident_id", "evidence_type"),
    )

    def __repr__(self):
        return f"<Evidence(id={self.id}, incident={self.incident_id}, type={self.evidence_type}, role={self.evidence_role})>"


class InvestigationAssessment(str, enum.Enum):
    STRONGLY_SUPPORTED = "strongly_supported"
    MODERATELY_SUPPORTED = "moderately_supported"
    WEAKLY_SUPPORTED = "weakly_supported"
    CONFLICTING = "conflicting"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INCONCLUSIVE = "inconclusive"


class IncidentInvestigation(Base):
    __tablename__ = "incident_investigations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supporting_evidence_count = Column(JSON, nullable=True, default=0)
    contradicting_evidence_count = Column(JSON, nullable=True, default=0)
    neutral_evidence_count = Column(JSON, nullable=True, default=0)
    uncertain_evidence_count = Column(JSON, nullable=True, default=0)
    evidence_confidence = Column(Float, nullable=True)  # Overall confidence score 0-1
    assessment = Column(SQLEnum(InvestigationAssessment), nullable=False)
    explanation = Column(Text, nullable=True)
    limitations = Column(Text, nullable=True)
    # Component scores
    source_diversity = Column(Float, nullable=True)
    geographic_consistency = Column(Float, nullable=True)
    temporal_consistency = Column(Float, nullable=True)
    multimodal_consistency = Column(Float, nullable=True)
    # AI metadata
    model_name = Column(String(200), nullable=True)
    investigated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_incident_investigations_incident_time", "incident_id", "investigated_at"),
    )

    def __repr__(self):
        return f"<IncidentInvestigation(id={self.id}, incident={self.incident_id}, assessment={self.assessment})>"