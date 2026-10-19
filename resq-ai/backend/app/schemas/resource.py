from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


ResourceType = Literal[
    "ambulance", "rescue_team", "fire_vehicle", "police_unit",
    "shelter", "hospital", "drone", "emergency_vehicle"
]

ResourceStatus = Literal[
    "available", "deployed", "unavailable", "maintenance", "unknown"
]


class ResourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    resource_type: ResourceType
    status: ResourceStatus = "unknown"
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: Optional[str] = None
    capacity: Optional[int] = Field(None, ge=0)
    current_load: Optional[int] = Field(None, ge=0)
    capabilities: Optional[Dict[str, Any]] = None
    organization: Optional[str] = Field(None, max_length=200)
    metadata: Optional[Dict[str, Any]] = None


class ResourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=500)
    resource_type: Optional[ResourceType] = None
    status: Optional[ResourceStatus] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    address: Optional[str] = None
    capacity: Optional[int] = Field(None, ge=0)
    current_load: Optional[int] = Field(None, ge=0)
    capabilities: Optional[Dict[str, Any]] = None
    organization: Optional[str] = Field(None, max_length=200)
    metadata: Optional[Dict[str, Any]] = None


class ResourceStatusUpdate(BaseModel):
    status: ResourceStatus


class ResourceResponse(BaseModel):
    id: UUID
    name: str
    resource_type: str
    status: str
    latitude: float
    longitude: float
    address: Optional[str]
    capacity: Optional[int]
    current_load: Optional[int]
    capabilities: Optional[Dict[str, Any]]
    organization: Optional[str]
    metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResourceListResponse(BaseModel):
    resources: List["ResourceResponse"]
    total: int
    limit: int
    offset: int


class NearbyResourceResponse(BaseModel):
    id: UUID
    name: str
    resource_type: str
    status: str
    distance_meters: float
    latitude: float
    longitude: float
    address: Optional[str]
    capacity: Optional[int]
    current_load: Optional[int]
    capabilities: Optional[Dict[str, Any]]
    organization: Optional[str]

    class Config:
        from_attributes = True


class NearbyResourceListResponse(BaseModel):
    resources: List[NearbyResourceResponse]
    total: int
    limit: int
    offset: int


class ResourceCountResponse(BaseModel):
    counts: Dict[str, int]


# Add forward reference resolution
ResourceListResponse.model_rebuild()