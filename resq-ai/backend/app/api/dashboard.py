"""
Dashboard Overview API (Phase 10).

Aggregated, read-only metrics for the Emergency Command Center landing page.
This module never recalculates risk, re-clusters incidents, re-investigates
evidence, or re-runs optimization. It only reads and counts data produced by
Phases 1-9.

Design notes
------------
* ``build_overview_payload`` is a pure function: it assembles the response from
  plain Python data and is unit-tested directly.
* ``gather_overview`` performs the database reads and returns the plain data.
  It always issues the same set of queries (empty ``IN`` clauses return no
  rows) so behaviour is deterministic.
* ``build_incidents_summary_payload`` is likewise pure.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.event import Event
from app.models.event_analysis import EventAIAnalysis
from app.models.evidence import IncidentInvestigation
from app.models.incident import Incident, IncidentStatus
from app.models.resource import Resource, ResourceStatus
from app.models.risk import (
    AllocationStatus,
    ImpactAssessment,
    OptimizationResult,
    ResourceAllocation,
    RiskAssessment,
    RiskLevel,
)
from app.schemas.dashboard import (
    DashboardOverview,
    IncidentSummaryResponse,
    PendingApproval,
    RecentEvent,
    RecentIncident,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

ANALYSIS_AWAITING = "pending"
ANALYSIS_COMPLETED = "completed"


# ---------------------------------------------------------------------------
# Small serialization helpers (pure)
# ---------------------------------------------------------------------------

def _enum_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _text_preview(text: Optional[str], limit: int = 160) -> Optional[str]:
    if not text:
        return None
    cleaned = " ".join(str(text).split())
    return cleaned[:limit] if cleaned else None


def _has_unmet_demand(unmet_demand: Any) -> bool:
    """True only when unmet demand is present and non-empty.

    The optimizer stores an empty list when every demand was met, so a bare
    ``is not None`` check would over-count. See Phase 8.
    """
    if unmet_demand is None:
        return False
    if isinstance(unmet_demand, (list, tuple, dict, set)):
        return len(unmet_demand) > 0
    return bool(unmet_demand)


def _latest_by_incident(rows: List[Any], attr: str = "incident_id") -> Dict[str, Any]:
    """Return the first (most recent) row per incident from a pre-sorted list."""
    result: Dict[str, Any] = {}
    for row in rows:
        key = str(getattr(row, attr))
        if key not in result:
            result[key] = row
    return result


# ---------------------------------------------------------------------------
# Metrics assembly (pure)
# ---------------------------------------------------------------------------

def build_overview_payload(data: Dict[str, Any]) -> DashboardOverview:
    """Assemble the overview response from plain gathered data.

    ``data`` keys: ``counts`` (dict of ints), ``recent_incidents``,
    ``recent_events``, ``pending_approvals``, ``with_unmet_demand``.
    """
    counts = data.get("counts", {})
    return DashboardOverview(
        generated_at=datetime.now(timezone.utc),
        incident_metrics={
            "total": counts.get("incidents_total", 0),
            "active": counts.get("incidents_active", 0),
            "emerging": counts.get("incidents_emerging", 0),
            "resolved": counts.get("incidents_resolved", 0),
            "critical_risk": counts.get("incidents_critical", 0),
            "high_risk": counts.get("incidents_high", 0),
            "recently_updated": counts.get("incidents_recent_24h", 0),
            "with_unmet_demand": data.get("with_unmet_demand", 0),
        },
        event_metrics={
            "total": counts.get("events_total", 0),
            "analyzed": counts.get("events_analyzed", 0),
            "awaiting_analysis": max(
                counts.get("events_total", 0) - counts.get("events_analyzed", 0), 0
            ),
            "recent_24h": counts.get("events_recent_24h", 0),
        },
        resource_metrics={
            "total": counts.get("resources_total", 0),
            "available": counts.get("resources_available", 0),
            "deployed": counts.get("resources_deployed", 0),
            "unavailable": counts.get("resources_unavailable", 0),
            "maintenance": counts.get("resources_maintenance", 0),
            "unknown": counts.get("resources_unknown", 0),
        },
        optimization_metrics={
            "incidents_with_optimization": counts.get("incidents_with_optimization", 0),
            "pending_approvals": counts.get("pending_approvals", 0),
            "approved_allocations": counts.get("approved_allocations", 0),
        },
        recent_incidents=[RecentIncident(**item) for item in data.get("recent_incidents", [])],
        recent_events=[RecentEvent(**item) for item in data.get("recent_events", [])],
        pending_approvals=[
            PendingApproval(**item) for item in data.get("pending_approvals", [])
        ],
    )


def build_incidents_summary_payload(
    items: List[Dict[str, Any]], total: int, limit: int, offset: int
) -> IncidentSummaryResponse:
    """Assemble the incident summary response from plain serialized items."""
    return IncidentSummaryResponse(
        incidents=items, total=total, limit=limit, offset=offset
    )


# ---------------------------------------------------------------------------
# Database gathering
# ---------------------------------------------------------------------------

async def _scalar(db: AsyncSession, stmt) -> int:
    result = await db.execute(stmt)
    value = result.scalar()
    return int(value or 0)


async def gather_overview(db: AsyncSession, limit_recent: int) -> Dict[str, Any]:
    """Read every number the Command Center needs. Read-only."""
    # Naive UTC to match the naive DateTime columns used across the models.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    day_ago = now - timedelta(hours=24)

    counts: Dict[str, int] = {}

    counts["incidents_total"] = await _scalar(db, select(func.count(Incident.id)))
    counts["incidents_active"] = await _scalar(
        db,
        select(func.count(Incident.id)).where(
            Incident.status.in_([IncidentStatus.EMERGING, IncidentStatus.ACTIVE])
        ),
    )
    counts["incidents_emerging"] = await _scalar(
        db, select(func.count(Incident.id)).where(Incident.status == IncidentStatus.EMERGING)
    )
    counts["incidents_resolved"] = await _scalar(
        db, select(func.count(Incident.id)).where(Incident.status == IncidentStatus.RESOLVED)
    )
    counts["incidents_recent_24h"] = await _scalar(
        db, select(func.count(Incident.id)).where(Incident.last_updated >= day_ago)
    )

    counts["incidents_critical"] = await _scalar(
        db,
        select(func.count(func.distinct(RiskAssessment.incident_id))).where(
            RiskAssessment.risk_level == RiskLevel.CRITICAL
        ),
    )
    counts["incidents_high"] = await _scalar(
        db,
        select(func.count(func.distinct(RiskAssessment.incident_id))).where(
            RiskAssessment.risk_level == RiskLevel.HIGH
        ),
    )

    counts["events_total"] = await _scalar(db, select(func.count(Event.id)))
    counts["events_recent_24h"] = await _scalar(
        db, select(func.count(Event.id)).where(Event.timestamp >= day_ago)
    )
    counts["events_analyzed"] = await _scalar(
        db, select(func.count(func.distinct(EventAIAnalysis.event_id)))
    )

    # Resources grouped by status (single query).
    counts["resources_total"] = 0
    for key in ("resources_available", "resources_deployed", "resources_unavailable",
                "resources_maintenance", "resources_unknown"):
        counts[key] = 0
    resource_rows = await db.execute(
        select(Resource.status, func.count(Resource.id)).group_by(Resource.status)
    )
    status_key = {
        ResourceStatus.AVAILABLE: "resources_available",
        ResourceStatus.DEPLOYED: "resources_deployed",
        ResourceStatus.UNAVAILABLE: "resources_unavailable",
        ResourceStatus.MAINTENANCE: "resources_maintenance",
        ResourceStatus.UNKNOWN: "resources_unknown",
    }
    for row_status, count in resource_rows.all():
        counts["resources_total"] += int(count or 0)
        bucket = status_key.get(row_status)
        if bucket:
            counts[bucket] = int(count or 0)

    counts["incidents_with_optimization"] = await _scalar(
        db, select(func.count(func.distinct(OptimizationResult.incident_id)))
    )
    counts["pending_approvals"] = await _scalar(
        db,
        select(func.count(ResourceAllocation.id)).where(
            ResourceAllocation.status == AllocationStatus.RECOMMENDED
        ),
    )
    counts["approved_allocations"] = await _scalar(
        db,
        select(func.count(ResourceAllocation.id)).where(
            ResourceAllocation.status == AllocationStatus.APPROVED
        ),
    )

    # Unmet demand: only count incidents whose *latest* run still has unmet demand.
    unmet_rows = (
        await db.execute(
            select(OptimizationResult)
            .order_by(OptimizationResult.created_at.desc())
        )
    ).scalars().all()
    unmet_by_incident: Dict[str, bool] = {}
    for opt in unmet_rows:
        key = str(opt.incident_id)
        if key not in unmet_by_incident:
            unmet_by_incident[key] = _has_unmet_demand(opt.unmet_demand)
    with_unmet_demand = sum(1 for v in unmet_by_incident.values() if v)

    # Recent incidents.
    recent_incidents = (
        await db.execute(
            select(Incident).order_by(Incident.last_updated.desc()).limit(limit_recent)
        )
    ).scalars().all()
    incident_ids = [i.id for i in recent_incidents]

    risk_map: Dict[str, RiskAssessment] = {}
    investigation_map: Dict[str, IncidentInvestigation] = {}
    if incident_ids:
        risk_rows = (
            await db.execute(
                select(RiskAssessment)
                .where(RiskAssessment.incident_id.in_(incident_ids))
                .order_by(RiskAssessment.assessed_at.desc())
            )
        ).scalars().all()
        risk_map = _latest_by_incident(risk_rows)

        inv_rows = (
            await db.execute(
                select(IncidentInvestigation)
                .where(IncidentInvestigation.incident_id.in_(incident_ids))
                .order_by(IncidentInvestigation.investigated_at.desc())
            )
        ).scalars().all()
        investigation_map = _latest_by_incident(inv_rows)

    serialized_incidents = []
    for inc in recent_incidents:
        key = str(inc.id)
        risk = risk_map.get(key)
        inv = investigation_map.get(key)
        serialized_incidents.append(
            {
                "id": inc.id,
                "title": inc.title,
                "incident_type": inc.incident_type,
                "status": _enum_value(inc.status),
                "risk_score": risk.risk_score if risk else None,
                "risk_level": _enum_value(risk.risk_level) if risk else None,
                "evidence_assessment": _enum_value(inv.assessment) if inv else None,
                "evidence_confidence": inv.evidence_confidence if inv else None,
                "event_count": inc.event_count or 0,
                "location_name": inc.location_name if hasattr(inc, "location_name") else None,
                "centroid_latitude": inc.centroid_latitude,
                "centroid_longitude": inc.centroid_longitude,
                "start_time": _iso(inc.start_time),
                "last_updated": _iso(inc.last_updated),
            }
        )

    # Recent events (explicit columns to avoid postgis geometry).
    recent_event_rows = (
        await db.execute(
            select(
                Event.id,
                Event.source,
                Event.event_type,
                Event.text_content,
                Event.location_name,
                Event.latitude,
                Event.longitude,
                Event.timestamp,
            )
            .order_by(Event.timestamp.desc())
            .limit(limit_recent)
        )
    ).all()
    event_ids = [row.id for row in recent_event_rows]
    analysis_map: Dict[str, Any] = {}
    if event_ids:
        analysis_rows = (
            await db.execute(
                select(EventAIAnalysis.event_id, EventAIAnalysis.disaster_type)
                .where(EventAIAnalysis.event_id.in_(event_ids))
                .order_by(EventAIAnalysis.created_at.desc())
            )
        ).all()
        for row in analysis_rows:
            key = str(row.event_id)
            if key not in analysis_map:
                analysis_map[key] = row.disaster_type

    serialized_events = []
    for row in recent_event_rows:
        key = str(row.id)
        analyzed = key in analysis_map
        serialized_events.append(
            {
                "id": row.id,
                "source": row.source,
                "event_type": row.event_type,
                "text_preview": _text_preview(row.text_content),
                "location_name": row.location_name,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "timestamp": _iso(row.timestamp),
                "analysis_status": ANALYSIS_COMPLETED if analyzed else ANALYSIS_AWAITING,
                "disaster_type": analysis_map.get(key),
            }
        )

    # Pending approvals.
    pending_allocations = (
        await db.execute(
            select(ResourceAllocation)
            .where(ResourceAllocation.status == AllocationStatus.RECOMMENDED)
            .order_by(ResourceAllocation.created_at.desc())
            .limit(limit_recent)
        )
    ).scalars().all()
    pending_incident_ids = list({a.incident_id for a in pending_allocations})
    pending_resource_ids = list({a.resource_id for a in pending_allocations})

    title_map = await _id_title_map(db, Incident, pending_incident_ids)
    resource_name_map = await _resource_name_map(db, pending_resource_ids)

    serialized_approvals = []
    for alloc in pending_allocations:
        serialized_approvals.append(
            {
                "allocation_id": alloc.id,
                "incident_id": alloc.incident_id,
                "incident_title": title_map.get(str(alloc.incident_id)),
                "resource_id": alloc.resource_id,
                "resource_name": resource_name_map.get(str(alloc.resource_id)),
                "resource_type": alloc.resource_type,
                "distance_meters": alloc.distance_meters,
                "assignment_reason": alloc.assignment_reason,
                "created_at": _iso(alloc.created_at),
            }
        )

    return {
        "counts": counts,
        "with_unmet_demand": with_unmet_demand,
        "recent_incidents": serialized_incidents,
        "recent_events": serialized_events,
        "pending_approvals": serialized_approvals,
    }


async def _id_title_map(db: AsyncSession, model, ids: List[UUID]) -> Dict[str, str]:
    if not ids:
        return {}
    rows = (await db.execute(select(model.id, model.title).where(model.id.in_(ids)))).all()
    return {str(r.id): r.title for r in rows}


async def _resource_name_map(db: AsyncSession, ids: List[UUID]) -> Dict[str, str]:
    if not ids:
        return {}
    rows = (await db.execute(select(Resource.id, Resource.name).where(Resource.id.in_(ids)))).all()
    return {str(r.id): r.name for r in rows}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/overview", response_model=DashboardOverview)
async def get_dashboard_overview(
    limit_recent: int = Query(
        default=settings.DASHBOARD_DEFAULT_PAGE_SIZE,
        ge=1,
        le=50,
        description="Maximum number of recent items per section.",
    ),
    db: AsyncSession = Depends(get_db),
) -> DashboardOverview:
    """Aggregated Command Center metrics from real backend data."""
    data = await gather_overview(db, limit_recent)
    return build_overview_payload(data)


def _validate_choice(value: Optional[str], allowed, field: str) -> Optional[str]:
    if value is None:
        return None
    if value not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {field}: {value}. Allowed: {sorted(allowed)}",
        )
    return value


@router.get("/incidents/summary", response_model=IncidentSummaryResponse)
async def get_incidents_summary(
    status_filter: Optional[str] = Query(None, alias="status"),
    incident_type: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    search: Optional[str] = Query(None, max_length=200, description="Match title or incident type"),
    sort_by: str = Query("last_updated", description="last_updated | risk_score | event_count"),
    order: str = Query("desc", description="asc | desc"),
    limit: int = Query(
        default=settings.DASHBOARD_DEFAULT_PAGE_SIZE,
        ge=1,
        le=settings.DASHBOARD_MAX_PAGE_SIZE,
    ),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> IncidentSummaryResponse:
    """Filterable, sortable, paginated incident summary for the incident panel."""
    if status_filter is not None:
        _validate_choice(status_filter, {s.value for s in IncidentStatus}, "status")
    if risk_level is not None:
        _validate_choice(risk_level, {r.value for r in RiskLevel}, "risk_level")
    _validate_choice(sort_by, {"last_updated", "risk_score", "event_count"}, "sort_by")
    _validate_choice(order, {"asc", "desc"}, "order")

    # Latest risk per incident (for filtering and sorting).
    latest_risk = (
        select(
            RiskAssessment.incident_id.label("incident_id"),
            func.max(RiskAssessment.assessed_at).label("max_at"),
        )
        .group_by(RiskAssessment.incident_id)
        .subquery()
    )

    query = select(Incident)
    if status_filter:
        query = query.where(Incident.status == IncidentStatus(status_filter))
    if incident_type:
        query = query.where(Incident.incident_type == incident_type)
    if search:
        like = f"%{search}%"
        query = query.where(Incident.title.ilike(like) | Incident.incident_type.ilike(like))

    risk_join = None
    if risk_level or sort_by == "risk_score":
        query = query.outerjoin(latest_risk, latest_risk.c.incident_id == Incident.id).outerjoin(
            RiskAssessment,
            (RiskAssessment.incident_id == latest_risk.c.incident_id)
            & (RiskAssessment.assessed_at == latest_risk.c.max_at),
        )
        risk_join = RiskAssessment
        if risk_level:
            query = query.where(RiskAssessment.risk_level == RiskLevel(risk_level))

    count_query = select(func.count()).select_from(query.subquery())
    total = int((await db.execute(count_query)).scalar() or 0)

    order_col = Incident.last_updated
    if sort_by == "risk_score" and risk_join is not None:
        order_col = RiskAssessment.risk_score
    elif sort_by == "event_count":
        order_col = Incident.event_count
    order_col = order_col.desc() if order == "desc" else order_col.asc()

    query = query.order_by(order_col).limit(limit).offset(offset)
    incidents = (await db.execute(query)).scalars().all()
    incident_ids = [i.id for i in incidents]

    risk_map: Dict[str, RiskAssessment] = {}
    investigation_map: Dict[str, IncidentInvestigation] = {}
    impact_map: Dict[str, ImpactAssessment] = {}
    if incident_ids:
        risk_map = _latest_by_incident(
            (
                await db.execute(
                    select(RiskAssessment)
                    .where(RiskAssessment.incident_id.in_(incident_ids))
                    .order_by(RiskAssessment.assessed_at.desc())
                )
            ).scalars().all()
        )
        investigation_map = _latest_by_incident(
            (
                await db.execute(
                    select(IncidentInvestigation)
                    .where(IncidentInvestigation.incident_id.in_(incident_ids))
                    .order_by(IncidentInvestigation.investigated_at.desc())
                )
            ).scalars().all()
        )
        impact_map = _latest_by_incident(
            (
                await db.execute(
                    select(ImpactAssessment)
                    .where(ImpactAssessment.incident_id.in_(incident_ids))
                    .order_by(ImpactAssessment.assessed_at.desc())
                )
            ).scalars().all()
        )

    items: List[Dict[str, Any]] = []
    for inc in incidents:
        key = str(inc.id)
        risk = risk_map.get(key)
        inv = investigation_map.get(key)
        impact = impact_map.get(key)
        items.append(
            {
                "id": inc.id,
                "title": inc.title,
                "incident_type": inc.incident_type,
                "status": _enum_value(inc.status),
                "event_count": inc.event_count or 0,
                "confidence": inc.confidence,
                "location_name": None,
                "centroid_latitude": inc.centroid_latitude,
                "centroid_longitude": inc.centroid_longitude,
                "start_time": inc.start_time,
                "last_updated": inc.last_updated,
                "risk_score": risk.risk_score if risk else None,
                "risk_level": _enum_value(risk.risk_level) if risk else None,
                "evidence_assessment": _enum_value(inv.assessment) if inv else None,
                "evidence_confidence": inv.evidence_confidence if inv else None,
                "population_potentially_exposed": (
                    impact.population_potentially_exposed if impact else None
                ),
            }
        )

    return build_incidents_summary_payload(items, total, limit, offset)
