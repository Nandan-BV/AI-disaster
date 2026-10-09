from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from uuid import UUID


RiskLevel = Literal["low", "moderate", "elevated", "high", "critical"]


class RecalculateRiskRequest(BaseModel):
    force: bool = False


class RiskAssessmentResponse(BaseModel):
    id: UUID
    incident_id: UUID
    risk_score: float = Field(..., ge=0, le=100)
    risk_level: RiskLevel
    severity_component: Optional[float] = Field(None, ge=0, le=100)
    evidence_component: Optional[float] = Field(None, ge=0, le=100)
    population_component: Optional[float] = Field(None, ge=0, le=100)
    infrastructure_component: Optional[float] = Field(None, ge=0, le=100)
    environment_component: Optional[float] = Field(None, ge=0, le=100)
    accessibility_component: Optional[float] = Field(None, ge=0, le=100)
    severity_details: Optional[Dict[str, Any]] = None
    evidence_details: Optional[Dict[str, Any]] = None
    population_details: Optional[Dict[str, Any]] = None
    infrastructure_details: Optional[Dict[str, Any]] = None
    environment_details: Optional[Dict[str, Any]] = None
    accessibility_details: Optional[Dict[str, Any]] = None
    explanation: Optional[str] = None
    model_name: Optional[str] = None
    assessed_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class RiskHistoryResponse(BaseModel):
    id: UUID
    incident_id: UUID
    risk_score: float
    risk_level: RiskLevel
    severity_component: Optional[float] = None
    evidence_component: Optional[float] = None
    population_component: Optional[float] = None
    infrastructure_component: Optional[float] = None
    environment_component: Optional[float] = None
    accessibility_component: Optional[float] = None
    explanation: Optional[str] = None
    trigger: Optional[str] = None
    assessed_at: datetime

    class Config:
        from_attributes = True


class ImpactAssessmentResponse(BaseModel):
    id: UUID
    incident_id: UUID
    population_potentially_exposed: Optional[int] = None
    population_zones_count: Optional[int] = None
    population_weighted_exposure: Optional[float] = None
    infrastructure_potentially_exposed: Optional[int] = None
    hospitals_count: Optional[int] = None
    shelters_count: Optional[int] = None
    fire_stations_count: Optional[int] = None
    police_stations_count: Optional[int] = None
    schools_count: Optional[int] = None
    bridges_count: Optional[int] = None
    roads_count: Optional[int] = None
    emergency_centers_count: Optional[int] = None
    power_stations_count: Optional[int] = None
    water_facilities_count: Optional[int] = None
    roads_potentially_affected: Optional[int] = None
    bridges_potentially_affected: Optional[int] = None
    accessibility_status: Optional[str] = None
    accessibility_details: Optional[Dict[str, Any]] = None
    explanation: Optional[str] = None
    assessed_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class IncidentInvestigationResponse(BaseModel):
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