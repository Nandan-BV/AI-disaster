from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from uuid import UUID


IncidentStatus = Literal["emerging", "active", "resolved"]


class IncidentEventResponse(BaseModel):
    id: UUID
    incident_id: UUID
    event_id: UUID
    similarity_score: Optional[float]
    geographic_distance_meters: Optional[float]
    temporal_distance_minutes: Optional[float]
    disaster_type_match: Optional[dict]
    assignment_confidence: Optional[float]
    relationship_components: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True


class IncidentResponse(BaseModel):
    id: UUID
    incident_type: Optional[str]
    title: str
    summary: Optional[str]
    centroid_latitude: Optional[float]
    centroid_longitude: Optional[float]
    start_time: datetime
    last_updated: datetime
    event_count: int
    status: IncidentStatus
    confidence: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IncidentDetailResponse(IncidentResponse):
    events: List[IncidentEventResponse] = Field(default_factory=list)


class IncidentListResponse(BaseModel):
    incidents: List[IncidentResponse]
    total: int
    limit: int
    offset: int


class ProcessEventResponse(BaseModel):
    incident_id: str
    action: str  # "created_new" or "added_to_existing"
    relationship_score: float
    incident_event_id: Optional[str] = None
    components: dict


class BatchProcessResponse(BaseModel):
    processed_events: int
    new_incidents: int
    updated_incidents: int
    errors: List[dict]