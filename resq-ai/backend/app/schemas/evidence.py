from datetime import datetime
from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


EvidenceType = Literal[
    "text", "image", "video", "geographic", "temporal",
    "multimodal", "consistency", "source_diversity"
]

EvidenceRole = Literal["supporting", "contradicting", "neutral", "uncertain"]

InvestigationAssessment = Literal[
    "strongly_supported", "moderately_supported", "weakly_supported",
    "conflicting", "insufficient_evidence", "inconclusive"
]


class EvidenceItem(BaseModel):
    id: UUID
    incident_id: UUID
    event_id: Optional[UUID]
    evidence_type: EvidenceType
    evidence_role: EvidenceRole
    description: str
    evidence_quality: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    source: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class EvidenceListResponse(BaseModel):
    evidence: List[EvidenceItem]
    total: int
    limit: int
    offset: int


class EvidenceInvestigation(BaseModel):
    incident_id: UUID
    supporting_evidence: List[EvidenceItem]
    contradicting_evidence: List[EvidenceItem]
    neutral_evidence: List[EvidenceItem]
    uncertain_evidence: List[EvidenceItem]
    source_diversity: Optional[float] = Field(None, ge=0.0, le=1.0)
    geographic_consistency: Optional[float] = Field(None, ge=0.0, le=1.0)
    temporal_consistency: Optional[float] = Field(None, ge=0.0, le=1.0)
    multimodal_consistency: Optional[float] = Field(None, ge=0.0, le=1.0)
    evidence_confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    assessment: InvestigationAssessment
    explanation: str
    limitations: Optional[str] = None
    model_name: Optional[str] = None
    investigated_at: datetime


class IncidentInvestigationResponse(BaseModel):
    id: UUID
    incident_id: UUID
    supporting_evidence_count: int
    contradicting_evidence_count: int
    neutral_evidence_count: int
    uncertain_evidence_count: int
    evidence_confidence: Optional[float]
    assessment: InvestigationAssessment
    explanation: Optional[str]
    limitations: Optional[str]
    source_diversity: Optional[float]
    geographic_consistency: Optional[float]
    temporal_consistency: Optional[float]
    multimodal_consistency: Optional[float]
    model_name: Optional[str]
    investigated_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class InvestigateRequest(BaseModel):
    force_rerun: bool = False