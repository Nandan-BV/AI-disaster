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

DemandPriority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

OptimizationStatus = Literal["optimal", "feasible", "infeasible", "no_solution", "error"]

AllocationStatus = Literal["recommended", "approved", "rejected", "cancelled"]


class ResourceDemandCreate(BaseModel):
    incident_id: UUID
    resource_type: ResourceType
    required_quantity: int = Field(..., ge=1, le=100)
    priority: DemandPriority = "MEDIUM"
    minimum_capability: Optional[Dict[str, bool]] = None


class ResourceDemandResponse(BaseModel):
    id: UUID
    incident_id: UUID
    resource_type: ResourceType
    required_quantity: int
    priority: DemandPriority
    minimum_capability: Optional[Dict[str, bool]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResourceDemandListResponse(BaseModel):
    demands: List[ResourceDemandResponse]
    total: int
    limit: int
    offset: int


class ResourceDemandCreateRequest(BaseModel):
    resource_type: ResourceType
    required_quantity: int = Field(..., ge=1, le=100)
    priority: DemandPriority = "MEDIUM"
    minimum_capability: Optional[Dict[str, bool]] = None


class ResourceDemandBatchCreateRequest(BaseModel):
    demands: List[dict]  # Using dict for simplicity


class EstimatedDemandItem(BaseModel):
    resource_type: ResourceType
    required_quantity: int
    priority: DemandPriority
    reason: str
    minimum_capability: Optional[Dict[str, bool]] = None


class DemandEstimationResponse(BaseModel):
    incident_id: UUID
    incident_type: Optional[str]
    risk_level: Optional[str]
    estimated_demands: List[dict]
    total_required: int


class ResourceDemandCreateRequest(BaseModel):
    resource_type: ResourceType
    required_quantity: int = Field(..., ge=1, le=100)
    priority: DemandPriority = "MEDIUM"
    minimum_capability: Optional[Dict[str, bool]] = None


class ResourceDemandBatchCreateRequest(BaseModel):
    demands: List[dict]


class ResourceAllocationCreate(BaseModel):
    optimization_result_id: UUID
    resource_id: UUID
    demand_id: UUID
    distance_meters: Optional[float] = None
    assignment_score: Optional[float] = None
    assignment_reason: Optional[str] = None


class ResourceAllocationStatusUpdate(BaseModel):
    status: str


class ResourceAllocationResponse(BaseModel):
    id: UUID
    optimization_result_id: UUID
    incident_id: UUID
    resource_id: UUID
    demand_id: Optional[UUID] = None
    resource_type: str
    distance_meters: Optional[float] = None
    assignment_score: Optional[float] = None
    assignment_reason: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResourceAllocationListResponse(BaseModel):
    allocations: List[dict]
    total: int
    limit: int
    offset: int


class OptimizationResultResponse(BaseModel):
    id: UUID
    incident_id: UUID
    status: str
    objective_value: Optional[float] = None
    total_distance: Optional[float] = None
    total_resources: int
    unmet_demand: List[dict] = []
    explanation: Optional[str] = None
    solver_name: Optional[str] = None
    solver_status: Optional[str] = None
    solver_time: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OptimizationResultDetailResponse(BaseModel):
    id: UUID
    incident_id: UUID
    status: str
    objective_value: Optional[float] = None
    total_distance: Optional[float] = None
    total_resources: int
    unmet_demand: List[dict] = []
    explanation: Optional[str] = None
    solver_name: Optional[str] = None
    solver_status: Optional[str] = None
    solver_time: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    allocations: List[dict] = []
    severity_component: Optional[float] = None
    evidence_component: Optional[float] = None
    population_component: Optional[float] = None
    infrastructure_component: Optional[float] = None
    environment_component: Optional[float] = None
    accessibility_component: Optional[float] = None
    severity_details: Optional[dict] = None
    evidence_details: Optional[dict] = None
    population_details: Optional[dict] = None
    infrastructure_details: Optional[dict] = None
    environment_details: Optional[dict] = None
    accessibility_details: Optional[dict] = None


class OptimizationResultListResponse(BaseModel):
    results: List[dict]
    total: int
    limit: int
    offset: int


class OptimizationRequest(BaseModel):
    incident_id: UUID
    force_rerun: bool = False


class RecalculateOptimizationRequest(BaseModel):
    force_rerun: bool = True


class OptimizationHistoryResponse(BaseModel):
    id: UUID
    incident_id: UUID
    optimization_result_id: UUID
    risk_score: float
    risk_level: str
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


class OptimizationHistoryListResponse(BaseModel):
    history: List[dict]
    total: int
    limit: int
    offset: int


class AllocationStatusUpdate(BaseModel):
    status: str


class AllocationStatusResponse(BaseModel):
    id: UUID
    incident_id: UUID
    optimization_result_id: UUID
    resource_id: UUID
    demand_id: Optional[UUID] = None
    distance_meters: Optional[float] = None
    assignment_score: Optional[float] = None
    assignment_reason: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True