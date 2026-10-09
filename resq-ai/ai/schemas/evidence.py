from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


EvidenceType = Literal[
    "text", "image", "video", "geographic", "temporal", "multimodal", "consistency", "source_diversity"
]

EvidenceRole = Literal["supporting", "contradicting", "neutral", "uncertain"]


class EvidenceItem(BaseModel):
    id: UUID
    incident_id: UUID
    event_id: Optional[UUID] = None
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


class EvidenceInvestigation(BaseModel):
    id: UUID
    incident_id: UUID
    supporting_evidence_count: int
    contradicting_evidence_count: int
    neutral_evidence_count: int
    uncertain_evidence_count: int
    evidence_confidence: float
    assessment: str
    explanation: str
    limitations: Optional[str] = None
    source_diversity: Optional[float] = None
    geographic_consistency: Optional[float] = None
    temporal_consistency: Optional[float] = None
    multimodal_consistency: Optional[float] = None
    model_name: Optional[str] = None
    investigated_at: datetime

    class Config:
        from_attributes = True


class InvestigateRequest(BaseModel):
    force_rerun: bool = False


class EvidenceInvestigationResponse(BaseModel):
    id: UUID
    incident_id: UUID
    supporting_evidence_count: int
    contradicting_evidence_count: int
    neutral_evidence_count: int
    uncertain_evidence_count: int
    evidence_confidence: float
    assessment: str
    explanation: str
    limitations: Optional[str] = None
    source_diversity: Optional[float] = None
    geographic_consistency: Optional[float] = None
    temporal_consistency: Optional[float] = None
    multimodal_consistency: Optional[float] = None
    model_name: Optional[str] = None
    investigated_at: datetime

    class Config:
        from_attributes = True


class EvidenceInvestigationResponse(BaseModel):
    id: UUID
    incident_id: UUID
    supporting_evidence: List[dict]
    contradicting_evidence: List[dict]
    neutral_evidence: List[dict]
    uncertain_evidence: List[dict]
    source_diversity: Optional[float] = None
    geographic_consistency: Optional[float] = None
    temporal_consistency: Optional[float] = None
    multimodal_consistency: Optional[float] = None
    evidence_confidence_score: Optional[float] = None
    assessment: str
    explanation: str
    limitations: Optional[str] = None
    model_name: Optional[str] = None
    investigated_at: datetime


class InvestigateRequest(BaseModel):
    force_rerun: bool = False