from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


InfrastructureType = Literal[
    "hospital", "shelter", "fire_station", "police_station",
    "school", "bridge", "road", "power_station",
    "water_facility", "emergency_center"
]

InfrastructureStatus = Literal[
    "operational", "partially_operational", "unavailable", "UNKNOWN"
]

RoadStatus = Literal[
    "open", "partially_blocked", "blocked", "unknown"
]


class InfrastructureCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    infrastructure_type: InfrastructureType
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: Optional[str] = None
    capacity: Optional[int] = Field(None, ge=0)
    status: InfrastructureStatus = "UNKNOWN"
    road_status: Optional[RoadStatus] = None
    metadata: Optional[dict] = None


class InfrastructureResponse(BaseModel):
    id: UUID
    name: str
    infrastructure_type: InfrastructureType
    latitude: float
    longitude: float
    address: Optional[str]
    capacity: Optional[int]
    status: InfrastructureStatus
    road_status: Optional[RoadStatus]
    metadata: Optional[dict]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NearbyInfrastructureResponse(BaseModel):
    id: UUID
    name: str
    infrastructure_type: InfrastructureType
    distance_meters: float
    latitude: float
    longitude: float
    status: InfrastructureStatus
    capacity: Optional[int]
    address: Optional[str]
    road_status: Optional[RoadStatus]
    metadata: Optional[dict]


class NearbyInfrastructureListResponse(BaseModel):
    infrastructure: List[NearbyInfrastructureResponse]
    total: int
    limit: int
    offset: int


class AffectedInfrastructureSummaryResponse(BaseModel):
    hospitals_nearby: List[NearbyInfrastructureResponse]
    shelters_nearby: List[NearbyInfrastructureResponse]
    fire_stations_nearby: List[NearbyInfrastructureResponse]
    police_stations_nearby: List[NearbyInfrastructureResponse]
    schools_nearby: List[NearbyInfrastructureResponse]
    bridges_nearby: List[NearbyInfrastructureResponse]
    roads_nearby: List[NearbyInfrastructureResponse]
    emergency_centers_nearby: List[NearbyInfrastructureResponse]
    power_stations_nearby: List[NearbyInfrastructureResponse]
    water_facilities_nearby: List[NearbyInfrastructureResponse]
    total_count: int


class IncidentLocationResponse(BaseModel):
    incident_id: UUID
    latitude: Optional[float]
    longitude: Optional[float]
    analysis_radius_meters: float


class IncidentAnalysisAreaResponse(BaseModel):
    incident_id: UUID
    radius_meters: float
    geometry: Optional[dict]  # GeoJSON
    created_at: datetime


class MapDataResponse(BaseModel):
    type: Literal["FeatureCollection"]
    features: List[dict]


class InfrastructureCountResponse(BaseModel):
    counts: dict