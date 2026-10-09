"""
Geospatial tools: incident location and nearby critical infrastructure.

Distance filtering runs in PostGIS (ST_DWithin) rather than in Python, and the
search radius is clamped to a configured maximum so a model cannot request an
unbounded scan. When PostGIS is unavailable the tool reports unavailability
instead of falling back to a straight-line approximation over every row.
"""

from typing import List, Optional
from uuid import UUID

from pydantic import Field
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
from app.models.infrastructure import (
    IncidentAnalysisArea,
    Infrastructure,
    InfrastructureType,
)
from app.models.incident import Incident


class GetIncidentLocationInput(IncidentRefInput):
    pass


class GetIncidentInfrastructureInput(IncidentRefInput):
    radius_meters: Optional[float] = Field(
        default=None,
        ge=0,
        description="Optional search radius in metres. Clamped to the configured maximum.",
    )
    infrastructure_type: Optional[str] = Field(
        default=None,
        description="Optional type filter, e.g. hospital, shelter, fire_station, bridge, road.",
    )
    limit: int = Field(default=50, ge=1, le=200)


def _valid_infra_types() -> set:
    return {item.value for item in InfrastructureType}


# Fixed statement. No user input is ever interpolated into SQL text; every value
# is passed as a bind parameter (spec 37).
_INFRASTRUCTURE_SQL = """
    SELECT
        infra.id::text                        AS id,
        infra.name                            AS name,
        infra.infrastructure_type::text       AS infrastructure_type,
        infra.status::text                    AS status,
        infra.road_status::text               AS road_status,
        infra.latitude                        AS latitude,
        infra.longitude                       AS longitude,
        infra.capacity                        AS capacity,
        infra.updated_at                      AS updated_at,
        ST_Distance(
            infra.location::geography,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
        ) AS distance_meters
    FROM infrastructure infra
    WHERE ST_DWithin(
              infra.location::geography,
              ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
              :radius
          )
    ORDER BY distance_meters ASC
    LIMIT :limit
"""


async def get_incident_location(incident_id: UUID) -> ToolResult:
    """Return the incident centroid and its configured analysis area."""
    db = current_session()
    incident_uuid(incident_id)

    incident = await db.get(Incident, incident_id)
    if incident is None:
        return ToolResult(
            available=False,
            source="Incident location (PostGIS)",
            notes=f"No incident found with id {incident_id}.",
        )

    area = (
        await db.execute(
            select(IncidentAnalysisArea).where(IncidentAnalysisArea.incident_id == incident_id)
        )
    ).scalar_one_or_none()

    data = {
        "incident_id": str(incident_id),
        "centroid": {
            "latitude": incident.centroid_latitude,
            "longitude": incident.centroid_longitude,
        },
        "analysis_area": (
            {"radius_meters": area.radius_meters, "defined": True} if area else
            {"radius_meters": None, "defined": False}
        ),
        "default_radius_meters": settings.DEFAULT_INCIDENT_RADIUS_METERS,
        "last_updated": jsonable(incident.last_updated),
        "data_age": age_description(incident.last_updated),
    }

    notes = None
    if incident.centroid_latitude is None or incident.centroid_longitude is None:
        notes = "This incident has no centroid; it cannot be used for spatial queries."
    elif area is None:
        notes = "No analysis area polygon is defined for this incident."

    return ToolResult(
        source="Incident location (PostGIS)",
        data_timestamp=incident.last_updated,
        data=data,
        notes=notes,
    )


async def get_incident_infrastructure(
    incident_id: UUID,
    radius_meters: Optional[float] = None,
    infrastructure_type: Optional[str] = None,
    limit: int = 50,
) -> ToolResult:
    """Return critical infrastructure within a radius of the incident centroid."""
    db = current_session()
    incident_uuid(incident_id)

    if infrastructure_type and infrastructure_type not in _valid_infra_types():
        return ToolResult(
            available=False,
            source="Infrastructure inventory (PostGIS)",
            notes=(
                f"Unknown infrastructure type {infrastructure_type!r}. "
                f"Allowed: {sorted(_valid_infra_types())}."
            ),
        )

    incident = await db.get(Incident, incident_id)
    if incident is None:
        return ToolResult(
            available=False,
            source="Infrastructure inventory (PostGIS)",
            notes=f"No incident found with id {incident_id}.",
        )
    if incident.centroid_latitude is None or incident.centroid_longitude is None:
        return ToolResult(
            available=False,
            source="Infrastructure inventory (PostGIS)",
            notes="This incident has no centroid, so no radius search can be performed.",
        )

    # Clamp rather than reject: a model asking for a huge radius should get a
    # bounded search, not a failure.
    max_radius = settings.MAX_INFRASTRUCTURE_RADIUS_METERS
    if radius_meters is None:
        radius_meters = min(
            settings.DEFAULT_INCIDENT_RADIUS_METERS, max_radius
        )
    radius_meters = min(float(radius_meters), float(max_radius))

    params = {
        "lat": incident.centroid_latitude,
        "lon": incident.centroid_longitude,
        "radius": radius_meters,
        "limit": limit,
    }

    type_filter = ""
    if infrastructure_type:
        # Compare against the enum's text representation rather than casting to
        # the enum type, whose internal SQLAlchemy name is an implementation
        # detail.
        type_filter = "AND infra.infrastructure_type::text = :infra_type"
        params["infra_type"] = infrastructure_type

    # ST_DWithin with geography casts gives true metre distances, and the
    # GiST index on location is used.
    query = _INFRASTRUCTURE_SQL if not type_filter else _INFRASTRUCTURE_SQL + " " + type_filter
    sql = text(query)

    try:
        rows = (await db.execute(sql, params)).mappings().all()
    except Exception as exc:  # noqa: BLE001
        # PostGIS may be absent in some deployments; be honest rather than
        # substituting a Python approximation.
        raise ToolError(
            "Infrastructure search could not be completed. The geospatial "
            f"query is unavailable on this deployment ({type(exc).__name__})."
        ) from exc

    if not rows:
        return ToolResult(
            source="Infrastructure inventory (PostGIS)",
            data={
                "incident_id": str(incident_id),
                "search_radius_meters": radius_meters,
                "radius_was_clamped": radius_meters == float(max_radius),
                "infrastructure_type": infrastructure_type,
                "infrastructure_count": 0,
                "counts_by_type": {},
                "infrastructure": [],
            },
            notes=(
                f"No infrastructure was found within {radius_meters:.0f} m. "
                "This is an empty result, not a statement that no critical "
                "infrastructure exists in the area."
            ),
        )

    items: List[dict] = []
    oldest = None
    for row in rows:
        updated_at = row.get("updated_at")
        if oldest is None or (updated_at and updated_at < oldest):
            oldest = updated_at
        items.append(
            {
                "id": row["id"],
                "name": row["name"],
                "infrastructure_type": row["infrastructure_type"],
                "status": row["status"],
                "road_status": row["road_status"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "capacity": row["capacity"],
                "distance_meters": (
                    round(float(row["distance_meters"]), 1)
                    if row["distance_meters"] is not None
                    else None
                ),
            }
        )

    by_type: dict = {}
    for item in items:
        by_type[item["infrastructure_type"]] = by_type.get(item["infrastructure_type"], 0) + 1

    return ToolResult(
        source="Infrastructure inventory (PostGIS)",
        data_timestamp=oldest,
        data={
            "incident_id": str(incident_id),
            "search_radius_meters": radius_meters,
            "radius_was_clamped": radius_meters == float(max_radius),
            "infrastructure_type": infrastructure_type,
            "infrastructure_count": len(items),
            "counts_by_type": by_type,
            "infrastructure": items,
        },
        notes=(
            "Distances are straight-line from the incident centroid within the "
            f"{radius_meters:.0f} m search radius."
        ),
    )
