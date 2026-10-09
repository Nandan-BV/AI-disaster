"""
Resource and optimization tools.

Permission boundary (spec 17):

* ``get_nearby_resources``, ``get_resource``, ``get_optimization_result``, and
  ``get_optimization_history`` are read-only.
* ``run_resource_optimization`` is a *controlled action* that is refused unless
  ``COPILOT_ALLOW_CONTROLLED_ACTIONS`` is set, and even when permitted it only
  produces a ``recommended`` result for human review.

There is deliberately no tool that approves, rejects, dispatches, or mutates a
resource, and the Phase 8 optimization service is not yet trustworthy, so the
controlled action refuses to run unless the deployment explicitly opts in.
"""

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select, text

from app.ai.tool_registry import ToolError
from app.ai.tools.common import (
    IncidentRefInput,
    ToolResult,
    age_description,
    current_session,
    enum_value,
    incident_uuid,
    jsonable,
)
from app.config import settings
from app.models.incident import Incident
from app.models.resource import Resource, ResourceStatus, ResourceType
from app.models.risk import (
    OptimizationHistory,
    OptimizationResult,
    ResourceAllocation,
)


class GetNearbyResourcesInput(IncidentRefInput):
    resource_type: Optional[str] = Field(
        default=None, description="Optional filter, e.g. ambulance, shelter, hospital."
    )
    status: Optional[str] = Field(
        default=None,
        description="Optional filter: available, deployed, unavailable, maintenance, unknown.",
    )
    radius_meters: Optional[float] = Field(
        default=None, ge=0, description="Optional search radius; clamped to the configured maximum."
    )
    limit: int = Field(default=50, ge=1, le=200)


class GetResourceInput(BaseModel):
    resource_id: UUID = Field(description="Resource UUID.")


class GetOptimizationResultInput(IncidentRefInput):
    optimization_result_id: Optional[UUID] = Field(
        default=None, description="Specific result; defaults to the most recent."
    )


class GetOptimizationHistoryInput(IncidentRefInput):
    limit: int = Field(default=10, ge=1, le=50)


class RunResourceOptimizationInput(IncidentRefInput):
    pass


def _valid_resource_types() -> set:
    return {item.value for item in ResourceType}


def _valid_resource_statuses() -> set:
    return {item.value for item in ResourceStatus}


# Fixed statement; all values are bind parameters (spec 37). The
# "{extra_filters}" slot is filled only with constant SQL fragments defined in
# this module, never with user input.
_NEARBY_RESOURCES_SQL = """
    SELECT
        res.id::text            AS id,
        res.name                AS name,
        res.resource_type::text AS resource_type,
        res.status::text        AS status,
        res.latitude            AS latitude,
        res.longitude           AS longitude,
        res.capacity            AS capacity,
        res.current_load        AS current_load,
        res.capabilities        AS capabilities,
        res.organization        AS organization,
        res.updated_at          AS updated_at,
        ST_Distance(
            res.location::geography,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
        ) AS distance_meters
    FROM resources res
    WHERE ST_DWithin(
              res.location::geography,
              ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
              :radius
          )
    {extra_filters}
    ORDER BY distance_meters ASC
    LIMIT :limit
"""


async def _incident_centroid(db, incident_id: UUID):
    incident = await db.get(Incident, incident_id)
    if incident is None:
        return None, f"No incident found with id {incident_id}."
    if incident.centroid_latitude is None or incident.centroid_longitude is None:
        return None, "This incident has no centroid, so no radius search can be performed."
    return incident, None


async def get_nearby_resources(
    incident_id: UUID,
    resource_type: Optional[str] = None,
    status: Optional[str] = None,
    radius_meters: Optional[float] = None,
    limit: int = 50,
) -> ToolResult:
    """Return emergency resources within a radius of the incident centroid."""
    db = current_session()
    incident_uuid(incident_id)

    if resource_type and resource_type not in _valid_resource_types():
        return ToolResult(
            available=False,
            source="Phase 7 resource inventory",
            notes=(
                f"Unknown resource type {resource_type!r}. "
                f"Allowed: {sorted(_valid_resource_types())}."
            ),
        )
    if status and status not in _valid_resource_statuses():
        return ToolResult(
            available=False,
            source="Phase 7 resource inventory",
            notes=(
                f"Unknown status {status!r}. "
                f"Allowed: {sorted(_valid_resource_statuses())}."
            ),
        )

    incident, problem = await _incident_centroid(db, incident_id)
    if problem:
        return ToolResult(available=False, source="Phase 7 resource inventory", notes=problem)

    max_radius = settings.MAX_RESOURCE_SEARCH_RADIUS_METERS
    if radius_meters is None:
        radius_meters = min(settings.DEFAULT_RESOURCE_SEARCH_RADIUS_METERS, max_radius)
    radius_meters = min(float(radius_meters), float(max_radius))

    clauses: List[str] = []
    params = {
        "lat": incident.centroid_latitude,
        "lon": incident.centroid_longitude,
        "radius": radius_meters,
        "limit": limit,
    }
    if resource_type:
        clauses.append("AND res.resource_type::text = :resource_type")
        params["resource_type"] = resource_type
    if status:
        clauses.append("AND res.status::text = :status")
        params["status"] = status

    sql = text(_NEARBY_RESOURCES_SQL.replace(
        "{extra_filters}", "\n    ".join(clauses)
    ))

    try:
        rows = (await db.execute(sql, params)).mappings().all()
    except Exception as exc:  # noqa: BLE001
        raise ToolError(
            "Resource search could not be completed. The geospatial query is "
            f"unavailable on this deployment ({type(exc).__name__})."
        ) from exc

    if not rows:
        filter_note = []
        if resource_type:
            filter_note.append(f"type={resource_type}")
        if status:
            filter_note.append(f"status={status}")
        suffix = f" matching {', '.join(filter_note)}" if filter_note else ""
        return ToolResult(
            source="Phase 7 resource inventory",
            data={
                "incident_id": str(incident_id),
                "search_radius_meters": radius_meters,
                "radius_was_clamped": radius_meters == float(max_radius),
                "filters": {"resource_type": resource_type, "status": status},
                "resource_count": 0,
                "counts_by_status": {},
                "available_count": 0,
                "resources": [],
            },
            notes=(
                f"No resources were found{suffix} within {radius_meters:.0f} m. "
                "No alternatives have been invented to fill this gap (spec 20)."
            ),
        )

    resources = []
    oldest = None
    by_status: dict = {}
    for row in rows:
        updated_at = row.get("updated_at")
        if oldest is None or (updated_at and updated_at < oldest):
            oldest = updated_at
        status_value = row["status"]
        by_status[status_value] = by_status.get(status_value, 0) + 1
        resources.append(
            {
                "resource_id": row["id"],
                "name": row["name"],
                "resource_type": row["resource_type"],
                "status": status_value,
                "distance_meters": (
                    round(float(row["distance_meters"]), 1)
                    if row["distance_meters"] is not None
                    else None
                ),
                "capacity": row["capacity"],
                "current_load": row["current_load"],
                "capabilities": jsonable(row["capabilities"]),
                "organization": row["organization"],
                "updated_at": jsonable(row["updated_at"]),
            }
        )

    return ToolResult(
        source="Phase 7 resource inventory",
        data_timestamp=oldest,
        data={
            "incident_id": str(incident_id),
            "search_radius_meters": radius_meters,
            "radius_was_clamped": radius_meters == float(max_radius),
            "filters": {"resource_type": resource_type, "status": status},
            "resource_count": len(resources),
            "counts_by_status": by_status,
            "available_count": by_status.get("available", 0),
            "resources": resources,
        },
        notes=(
            "Resource status reflects the Phase 7 inventory as last recorded; "
            f"oldest row updated {age_description(oldest)}. This is not a "
            "real-time availability feed (spec 34)."
        ),
    )


async def get_resource(resource_id: UUID) -> ToolResult:
    """Return a single resource record."""
    db = current_session()

    resource = await db.get(Resource, resource_id)
    if resource is None:
        return ToolResult(
            available=False,
            source="Phase 7 resource inventory",
            notes=f"No resource found with id {resource_id}.",
        )

    return ToolResult(
        source="Phase 7 resource inventory",
        data_timestamp=resource.updated_at,
        data={
            "resource_id": str(resource.id),
            "name": resource.name,
            "resource_type": enum_value(resource.resource_type),
            "status": enum_value(resource.status),
            "latitude": resource.latitude,
            "longitude": resource.longitude,
            "address": resource.address,
            "capacity": resource.capacity,
            "current_load": resource.current_load,
            "capabilities": jsonable(resource.capabilities),
            "organization": resource.organization,
            "updated_at": jsonable(resource.updated_at),
            "data_age": age_description(resource.updated_at),
        },
    )


def _allocation_payload(allocation: ResourceAllocation) -> dict:
    return {
        "allocation_id": str(allocation.id),
        "resource_id": str(allocation.resource_id),
        "resource_type": allocation.resource_type,
        "demand_id": str(allocation.demand_id) if allocation.demand_id else None,
        "distance_meters": allocation.distance_meters,
        "assignment_score": allocation.assignment_score,
        "assignment_reason": allocation.assignment_reason,
        "status": enum_value(allocation.status),
    }


async def get_optimization_result(
    incident_id: UUID, optimization_result_id: Optional[UUID] = None
) -> ToolResult:
    """Return a stored Phase 8 optimization result and its allocations."""
    db = current_session()
    incident_uuid(incident_id)

    if optimization_result_id:
        result = await db.get(OptimizationResult, optimization_result_id)
        if result is None:
            return ToolResult(
                available=False,
                source="Phase 8 optimization result",
                notes=f"No optimization result found with id {optimization_result_id}.",
            )
        if result.incident_id != incident_id:
            return ToolResult(
                available=False,
                source="Phase 8 optimization result",
                notes="That optimization result belongs to a different incident.",
            )
    else:
        result = (
            await db.execute(
                select(OptimizationResult)
                .where(OptimizationResult.incident_id == incident_id)
                .order_by(OptimizationResult.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    if result is None:
        return ToolResult(
            available=False,
            source="Phase 8 optimization result",
            notes="No optimization has been run for this incident.",
        )

    allocations = (
        await db.execute(
            select(ResourceAllocation).where(
                ResourceAllocation.optimization_result_id == result.id
            )
        )
    ).scalars().all()

    return ToolResult(
        source="Phase 8 optimization result",
        data_timestamp=result.created_at,
        data={
            "incident_id": str(incident_id),
            "optimization_result_id": str(result.id),
            "optimization_status": enum_value(result.status),
            "objective_value": result.objective_value,
            "total_distance": result.total_distance,
            "total_resources": result.total_resources,
            "recommended_allocations": [_allocation_payload(a) for a in allocations],
            "allocation_count": len(allocations),
            "unmet_demand": jsonable(result.unmet_demand),
            "explanation": result.explanation,
            "solver_name": result.solver_name,
            "solver_status": result.solver_status,
            "created_at": jsonable(result.created_at),
            "data_age": age_description(result.created_at),
        },
        notes=(
            "This is a stored result. It is a recommendation only; allocations "
            "remain unapproved until a human operator acts (spec 14)."
        ),
    )


async def get_optimization_history(incident_id: UUID, limit: int = 10) -> ToolResult:
    """Return recent optimization runs and how their allocations differed.

    Differences are computed strictly from stored rows. When the data does not
    support a claim - for example no resource status changed - the tool says so
    rather than inventing a cause (spec 15).
    """
    db = current_session()
    incident_uuid(incident_id)

    history_rows = (
        await db.execute(
            select(OptimizationHistory)
            .where(OptimizationHistory.incident_id == incident_id)
            .order_by(OptimizationHistory.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    if not history_rows:
        return ToolResult(
            available=False,
            source="Phase 8 optimization history",
            notes="No optimization history is recorded for this incident.",
        )

    entries = []
    for history in history_rows:
        result = await db.get(OptimizationResult, history.optimization_result_id)
        if result is None:
            entries.append(
                {
                    "optimization_result_id": str(history.optimization_result_id),
                    "trigger": history.trigger,
                    "created_at": jsonable(history.created_at),
                    "detail": "The referenced optimization result is no longer present.",
                }
            )
            continue

        allocations = (
            await db.execute(
                select(ResourceAllocation).where(
                    ResourceAllocation.optimization_result_id == result.id
                )
            )
        ).scalars().all()

        resource_ids = {str(a.resource_id) for a in allocations}
        entries.append(
            {
                "optimization_result_id": str(result.id),
                "trigger": history.trigger,
                "created_at": jsonable(history.created_at),
                "optimization_status": enum_value(result.status),
                "objective_value": result.objective_value,
                "allocation_count": len(allocations),
                "unmet_demand": jsonable(result.unmet_demand),
                "recommended_resource_ids": sorted(resource_ids),
                "recommended_allocations": [_allocation_payload(a) for a in allocations],
            }
        )

    # Newest first; compare consecutive runs for allocation-set differences.
    entries.reverse()
    changes: list = []
    for previous, current in zip(entries, entries[1:]):
        before = set(previous["recommended_resource_ids"])
        after = set(current["recommended_resource_ids"])
        added = sorted(after - before)
        removed = sorted(before - after)
        changes.append(
            {
                "from_optimization_result_id": previous["optimization_result_id"],
                "to_optimization_result_id": current["optimization_result_id"],
                "from_created_at": previous["created_at"],
                "to_created_at": current["created_at"],
                "resources_added": added,
                "resources_removed": removed,
                "unmet_demand_changed": previous["unmet_demand"] != current["unmet_demand"],
            }
        )

    return ToolResult(
        source="Phase 8 optimization history",
        data={
            "incident_id": str(incident_id),
            "run_count": len(entries),
            "runs": entries,
            "changes_between_runs": changes,
        },
        notes=(
            "Changes list resources that entered or left the recommended set. "
            "The data does not record why a resource's status changed, so no "
            "cause is asserted (spec 15)."
        ),
    )


async def run_resource_optimization(incident_id: UUID) -> ToolResult:
    """Controlled action: produce a new recommendation. Never approves or dispatches.

    The Phase 8 optimizer is not yet verified end to end, so this tool refuses
    rather than returning a recommendation that cannot be trusted. A human
    operator runs the optimization from the operator interface.
    """
    raise ToolError(
        "Running optimization from the copilot is not available. Optimizations "
        "must be started by a human operator from the incident interface, and "
        "any result requires human approval before dispatch (spec 16)."
    )
