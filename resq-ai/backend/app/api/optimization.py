import uuid
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.config import settings
from app.models.incident import Incident, IncidentEvent
from app.models.resource import Resource
from app.models.risk import (
    ResourceDemand, OptimizationResult, ResourceAllocation, OptimizationHistory,
    OptimizationStatus, AllocationStatus, EnvironmentalConditions, ImpactAssessment,
    RiskAssessment,
)
from app.models.event import Event
from app.models.event_analysis import EventAIAnalysis
from app.models.infrastructure import Infrastructure
from app.services.demand_service import DemandEstimationService
from app.services.resource_service import ResourceService
from app.optimization.resource_optimizer import ResourceOptimizer

router = APIRouter(prefix="/incidents", tags=["optimization"])


@router.post("/{incident_id}/optimize-resources", response_model=dict, status_code=status.HTTP_201_CREATED)
async def run_optimization(
    incident_id: UUID,
    request: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Run resource optimization for an incident.

    This endpoint:
    1. Retrieves incident and related data
    2. Generates resource demand estimates
    3. Finds eligible nearby resources
    4. Runs OR-Tools CP-SAT optimization
    5. Stores optimization result and allocations
    6. Returns recommendation (operator must approve — copilot never dispatches)
    """
    # Verify incident exists
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with id {incident_id} not found",
        )

    force_rerun = request.get("force_rerun", False) if request else False

    if not force_rerun:
        existing_result = await db.execute(
            select(OptimizationResult)
            .where(OptimizationResult.incident_id == incident_id)
            .order_by(OptimizationResult.created_at.desc())
            .limit(1)
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            return _format_optimization_result(existing, [])

    # Validate coordinates
    if not incident.centroid_latitude or not incident.centroid_longitude:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Incident {incident_id} has no valid coordinates",
        )

    # Fetch risk assessment
    risk_result = await db.execute(
        select(RiskAssessment)
        .where(RiskAssessment.incident_id == incident_id)
        .order_by(RiskAssessment.created_at.desc())
        .limit(1)
    )
    risk_assessment = risk_result.scalar_one_or_none()

    # Fetch impact assessment
    impact_result = await db.execute(
        select(ImpactAssessment)
        .where(ImpactAssessment.incident_id == incident_id)
        .order_by(ImpactAssessment.assessed_at.desc())
        .limit(1)
    )
    impact_assessment = impact_result.scalar_one_or_none()

    # Fetch AI analysis for the most recent event in this incident
    events_result = await db.execute(
        select(Event)
        .join(IncidentEvent, Event.id == IncidentEvent.event_id)
        .where(IncidentEvent.incident_id == incident_id)
    )
    events = list(events_result.scalars().all())
    event_ids = [e.id for e in events]

    ai_analysis = None
    if event_ids:
        ai_result = await db.execute(
            select(EventAIAnalysis)
            .where(EventAIAnalysis.event_id.in_(event_ids))
            .order_by(EventAIAnalysis.created_at.desc())
            .limit(1)
        )
        ai_analysis = ai_result.scalar_one_or_none()

    # Fetch environmental conditions
    env_result = await db.execute(
        select(EnvironmentalConditions)
        .where(EnvironmentalConditions.incident_id == incident_id)
        .order_by(EnvironmentalConditions.timestamp.desc())
        .limit(1)
    )
    env_conditions = env_result.scalar_one_or_none()

    # Step 1: Estimate resource demands
    demand_service = DemandEstimationService()
    estimated_demands_raw = await demand_service.estimate_demands(
        incident_id=str(incident_id),
        db=db,
        incident_type=incident.incident_type,
        risk_assessment=risk_assessment,
        impact_assessment=impact_assessment,
        env_conditions=env_conditions,
        ai_analysis=ai_analysis,
    )

    if not estimated_demands_raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not estimate resource demands for this incident",
        )

    # Step 2: Find eligible nearby resources (use the Resource table, not Infrastructure)
    resources_result = await db.execute(
        select(Resource).where(Resource.status == "available")
    )
    available_resources = list(resources_result.scalars().all())

    # Convert resources to optimizer format
    nearby_resources = []
    for res in available_resources:
        nearby_resources.append({
            "id": str(res.id),
            "name": res.name,
            "resource_type": res.resource_type if isinstance(res.resource_type, str) else res.resource_type.value,
            "latitude": res.latitude,
            "longitude": res.longitude,
            "status": res.status if isinstance(res.status, str) else res.status.value,
            "capabilities": res.metadata or {},
            "capacity": res.capacity or 1,
            "current_load": 0,
        })

    # Convert estimated demands to optimizer format, generating proper UUIDs
    demands = []
    for demand in estimated_demands_raw:
        demands.append({
            "demand_id": str(uuid.uuid4()),
            "resource_type": demand["resource_type"],
            "required_quantity": demand["required_quantity"],
            "priority": demand["priority"],
            "required_capabilities": demand.get("minimum_capability", {}),
        })

    # Step 3: Run optimization
    optimizer = ResourceOptimizer(time_limit_seconds=settings.OPT_SOLVER_TIME_LIMIT_SECONDS)
    opt_output = optimizer.solve(
        demands=demands,
        resources=nearby_resources,
        incident_location=(incident.centroid_latitude, incident.centroid_longitude),
        weights={
            "distance": settings.OPT_WEIGHT_DISTANCE,
            "suitability": settings.OPT_WEIGHT_SUITABILITY,
            "unmet_demand": settings.OPT_WEIGHT_UNMET_DEMAND,
            "priority": settings.OPT_WEIGHT_PRIORITY,
        },
        max_distance=settings.MAX_RESOURCE_ALLOCATION_DISTANCE_METERS,
    )

    if opt_output.get("status") == "ERROR":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Optimization failed: {opt_output.get('explanation', 'Unknown error')}",
        )

    # Map solver status string → OptimizationStatus enum
    solver_status_str = (opt_output.get("solver_status") or "no_solution").lower()
    status_map = {
        "optimal": OptimizationStatus.OPTIMAL,
        "feasible": OptimizationStatus.FEASIBLE,
        "infeasible": OptimizationStatus.INFEASIBLE,
        "no_solution": OptimizationStatus.NO_SOLUTION,
        "error": OptimizationStatus.ERROR,
        "unknown": OptimizationStatus.NO_SOLUTION,
        "success": OptimizationStatus.FEASIBLE,
    }
    db_status = status_map.get(solver_status_str, OptimizationStatus.NO_SOLUTION)

    # Step 4: Persist optimization result
    opt_result = OptimizationResult(
        incident_id=incident_id,
        status=db_status,
        objective_value=opt_output.get("objective_value"),
        total_distance=opt_output.get("total_distance"),
        total_resources=opt_output.get("total_resources", 0),
        unmet_demand=opt_output.get("unmet_demand", []),
        explanation=opt_output.get("explanation"),
        solver_name="OR-Tools CP-SAT",
        solver_status=opt_output.get("solver_status", "NO_SOLUTION"),
    )
    db.add(opt_result)
    await db.flush()

    # Step 5: Persist allocations (only for resources that exist in the resources table)
    resource_id_set = {str(r.id): r for r in available_resources}
    saved_allocations = []
    for alloc in opt_output.get("allocations", []):
        rid = alloc.get("resource_id")
        if rid not in resource_id_set:
            # Resource came from infrastructure — skip FK constraint violation
            continue
        allocation = ResourceAllocation(
            optimization_result_id=opt_result.id,
            incident_id=incident_id,
            resource_id=UUID(rid),
            resource_type=alloc.get("resource_type", "unknown"),
            distance_meters=alloc.get("distance_meters"),
            assignment_score=alloc.get("assignment_score"),
            assignment_reason=alloc.get("assignment_reason") or alloc.get("reason"),
            status=AllocationStatus.RECOMMENDED,
        )
        db.add(allocation)
        saved_allocations.append(allocation)

    # Step 6: Log optimization history entry
    history_entry = OptimizationHistory(
        incident_id=incident_id,
        optimization_result_id=opt_result.id,
        trigger="manual",
    )
    db.add(history_entry)

    await db.commit()
    await db.refresh(opt_result)

    return _format_optimization_result(opt_result, saved_allocations)


@router.get("/{incident_id}/optimization", response_model=dict)
async def get_optimization(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the latest optimization result for an incident."""
    result = await db.execute(
        select(OptimizationResult)
        .where(OptimizationResult.incident_id == incident_id)
        .order_by(OptimizationResult.created_at.desc())
        .limit(1)
    )
    optimization = result.scalar_one_or_none()

    if not optimization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No optimization found for incident {incident_id}. Run POST /incidents/{incident_id}/optimize-resources first.",
        )

    alloc_result = await db.execute(
        select(ResourceAllocation)
        .where(ResourceAllocation.optimization_result_id == optimization.id)
    )
    allocations = list(alloc_result.scalars().all())

    return _format_optimization_result(optimization, allocations)


@router.post("/{incident_id}/optimize-resources/recalculate", response_model=dict)
async def recalculate_optimization(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Recalculate optimization using the latest data."""
    return await run_optimization(incident_id, {"force_rerun": True}, db)


@router.get("/{incident_id}/optimization/history", response_model=list)
async def get_optimization_history(
    incident_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get the optimization run history for an incident."""
    result = await db.execute(
        select(OptimizationHistory)
        .where(OptimizationHistory.incident_id == incident_id)
        .order_by(OptimizationHistory.created_at.desc())
        .limit(limit)
    )
    history = list(result.scalars().all())

    return [
        {
            "id": str(h.id),
            "incident_id": str(h.incident_id),
            "optimization_result_id": str(h.optimization_result_id),
            "trigger": h.trigger,
            "created_at": h.created_at.isoformat() if h.created_at else None,
        }
        for h in history
    ]


@router.get("/{incident_id}/optimization/{optimization_id}/allocations", response_model=list)
async def get_optimization_allocations(
    incident_id: UUID,
    optimization_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all allocations for a specific optimization result."""
    result = await db.execute(
        select(ResourceAllocation)
        .where(ResourceAllocation.optimization_result_id == optimization_id)
        .where(ResourceAllocation.incident_id == incident_id)
    )
    allocations = list(result.scalars().all())

    return [_format_allocation(a) for a in allocations]


@router.patch("/resource-allocations/{allocation_id}/status", response_model=dict)
async def update_allocation_status(
    allocation_id: UUID,
    status_update: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Update the status of a resource allocation (approve / reject / cancel).
    Operators approve or reject recommendations — the copilot never does this.
    """
    result = await db.execute(
        select(ResourceAllocation).where(ResourceAllocation.id == allocation_id)
    )
    allocation = result.scalar_one_or_none()

    if not allocation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Allocation {allocation_id} not found",
        )

    new_status = status_update.get("status")
    if not new_status:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="'status' field is required",
        )

    valid_transitions = {
        "recommended": ["approved", "rejected"],
        "approved": ["cancelled"],
        "rejected": ["recommended"],
        "cancelled": ["recommended"],
    }

    current = allocation.status if isinstance(allocation.status, str) else allocation.status.value
    if current not in valid_transitions or new_status not in valid_transitions.get(current, []):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status transition from '{current}' to '{new_status}'",
        )

    allocation.status = AllocationStatus(new_status)
    allocation.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(allocation)

    return _format_allocation(allocation)


# ---------------------------------------------------------------------------
# Private helper formatters
# ---------------------------------------------------------------------------

def _format_optimization_result(opt: OptimizationResult, allocations: list) -> dict:
    return {
        "id": str(opt.id),
        "incident_id": str(opt.incident_id),
        "status": opt.status.value if hasattr(opt.status, "value") else opt.status,
        "objective_value": opt.objective_value,
        "total_distance": opt.total_distance,
        "total_resources": opt.total_resources,
        "unmet_demand": opt.unmet_demand,
        "explanation": opt.explanation,
        "solver_name": opt.solver_name,
        "solver_status": opt.solver_status,
        "created_at": opt.created_at.isoformat() if opt.created_at else None,
        "allocations": [_format_allocation(a) for a in allocations],
    }


def _format_allocation(a: ResourceAllocation) -> dict:
    return {
        "id": str(a.id),
        "incident_id": str(a.incident_id),
        "optimization_result_id": str(a.optimization_result_id),
        "resource_id": str(a.resource_id),
        "resource_type": a.resource_type,
        "distance_meters": a.distance_meters,
        "assignment_score": a.assignment_score,
        "assignment_reason": a.assignment_reason,
        "status": a.status.value if hasattr(a.status, "value") else a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
