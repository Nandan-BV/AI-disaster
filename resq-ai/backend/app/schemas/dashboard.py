"""
Command Center dashboard schemas (Phase 10).

These models describe the aggregated payloads served by ``/dashboard/*``.
They are the contract the frontend consumes; every number here maps to a
real database query (see ``app/api/dashboard.py``). Nothing is fabricated.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class IncidentMetrics(BaseModel):
    total: int = 0
    active: int = 0
    emerging: int = 0
    resolved: int = 0
    critical_risk: int = 0
    high_risk: int = 0
    recently_updated: int = 0
    with_unmet_demand: int = 0


class EventMetrics(BaseModel):
    total: int = 0
    analyzed: int = 0
    awaiting_analysis: int = 0
    recent_24h: int = 0


class ResourceMetrics(BaseModel):
    total: int = 0
    available: int = 0
    deployed: int = 0
    unavailable: int = 0
    maintenance: int = 0
    unknown: int = 0


class OptimizationMetrics(BaseModel):
    incidents_with_optimization: int = 0
    pending_approvals: int = 0
    approved_allocations: int = 0


class RecentIncident(BaseModel):
    id: UUID
    title: str
    incident_type: Optional[str] = None
    status: str
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    evidence_assessment: Optional[str] = None
    evidence_confidence: Optional[float] = None
    event_count: int = 0
    location_name: Optional[str] = None
    centroid_latitude: Optional[float] = None
    centroid_longitude: Optional[float] = None
    start_time: Optional[datetime] = None
    last_updated: Optional[datetime] = None


class RecentEvent(BaseModel):
    id: UUID
    source: str
    event_type: Optional[str] = None
    text_preview: Optional[str] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timestamp: Optional[datetime] = None
    analysis_status: str = "pending"
    disaster_type: Optional[str] = None
    incident_id: Optional[UUID] = None


class PendingApproval(BaseModel):
    allocation_id: UUID
    incident_id: UUID
    incident_title: Optional[str] = None
    resource_id: Optional[UUID] = None
    resource_name: Optional[str] = None
    resource_type: str
    distance_meters: Optional[float] = None
    assignment_reason: Optional[str] = None
    created_at: Optional[datetime] = None


class DashboardOverview(BaseModel):
    generated_at: datetime
    incident_metrics: IncidentMetrics = Field(default_factory=IncidentMetrics)
    event_metrics: EventMetrics = Field(default_factory=EventMetrics)
    resource_metrics: ResourceMetrics = Field(default_factory=ResourceMetrics)
    optimization_metrics: OptimizationMetrics = Field(default_factory=OptimizationMetrics)
    recent_incidents: List[RecentIncident] = Field(default_factory=list)
    recent_events: List[RecentEvent] = Field(default_factory=list)
    pending_approvals: List[PendingApproval] = Field(default_factory=list)


class IncidentSummaryItem(BaseModel):
    id: UUID
    title: str
    incident_type: Optional[str] = None
    status: str
    event_count: int = 0
    confidence: Optional[float] = None
    location_name: Optional[str] = None
    centroid_latitude: Optional[float] = None
    centroid_longitude: Optional[float] = None
    start_time: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    evidence_assessment: Optional[str] = None
    evidence_confidence: Optional[float] = None
    population_potentially_exposed: Optional[int] = None


class IncidentSummaryResponse(BaseModel):
    incidents: List[IncidentSummaryItem] = Field(default_factory=list)
    total: int = 0
    limit: int = 0
    offset: int = 0
