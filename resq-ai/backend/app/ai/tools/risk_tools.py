"""
Risk and impact tools.

These tools only *read* the Phase 6 assessments. The copilot explains the stored
components and never recomputes a score, so the copilot cannot introduce a
second, divergent notion of severity (spec 11, 29).
"""

from uuid import UUID

from sqlalchemy import select

from app.ai.tools.common import (
    IncidentRefInput,
    ToolResult,
    age_description,
    current_session,
    enum_value,
    incident_uuid,
    jsonable,
)
from app.models.risk import ImpactAssessment, RiskAssessment


class GetIncidentRiskInput(IncidentRefInput):
    pass


class GetIncidentImpactInput(IncidentRefInput):
    pass


async def _latest(db, model, incident_id: UUID, order_column):
    return (
        await db.execute(
            select(model)
            .where(model.incident_id == incident_id)
            .order_by(order_column.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def get_incident_risk(incident_id: UUID) -> ToolResult:
    """Return the latest stored risk assessment with its component scores."""
    db = current_session()
    incident_uuid(incident_id)

    assessment = await _latest(db, RiskAssessment, incident_id, RiskAssessment.assessed_at)
    if assessment is None:
        return ToolResult(
            available=False,
            source="Phase 6 risk assessment",
            notes="No risk assessment has been computed for this incident.",
        )

    return ToolResult(
        source="Phase 6 risk assessment",
        data_timestamp=assessment.assessed_at,
        data={
            "incident_id": str(incident_id),
            "risk_score": assessment.risk_score,
            "risk_level": enum_value(assessment.risk_level),
            # Column is `environment_component`; the tool exposes the spec name.
            "environmental_component": assessment.environment_component,
            "severity_component": assessment.severity_component,
            "evidence_component": assessment.evidence_component,
            "population_component": assessment.population_component,
            "infrastructure_component": assessment.infrastructure_component,
            "accessibility_component": assessment.accessibility_component,
            "explanation": assessment.explanation,
            "model_name": assessment.model_name,
            "assessed_at": jsonable(assessment.assessed_at),
            "updated_at": jsonable(assessment.updated_at),
            "data_age": age_description(assessment.assessed_at),
        },
        notes=(
            "Component scores are 0-100 and sum toward the stored risk score. "
            "They are reported as computed by Phase 6, not re-evaluated here."
        ),
    )


async def get_incident_impact(incident_id: UUID) -> ToolResult:
    """Return the latest stored impact assessment."""
    db = current_session()
    incident_uuid(incident_id)

    assessment = await _latest(db, ImpactAssessment, incident_id, ImpactAssessment.assessed_at)
    if assessment is None:
        return ToolResult(
            available=False,
            source="Phase 6 impact assessment",
            notes="No impact assessment has been computed for this incident.",
        )

    return ToolResult(
        source="Phase 6 impact assessment",
        data_timestamp=assessment.assessed_at,
        data={
            "incident_id": str(incident_id),
            "population_potentially_exposed": assessment.population_potentially_exposed,
            "population_zones_count": assessment.population_zones_count,
            "infrastructure_potentially_exposed": assessment.infrastructure_potentially_exposed,
            "hospitals_count": assessment.hospitals_count,
            "shelters_count": assessment.shelters_count,
            "roads_count": assessment.roads_count,
            "bridges_count": assessment.bridges_count,
            "accessibility_status": assessment.accessibility_status,
            "accessibility_details": jsonable(assessment.accessibility_details),
            "explanation": assessment.explanation,
            "assessed_at": jsonable(assessment.assessed_at),
            "data_age": age_description(assessment.assessed_at),
        },
        notes=(
            "Population and infrastructure figures are potentially-exposed "
            "estimates within the configured analysis area. They do not mean "
            "every person or structure in the area is affected (spec 12)."
        ),
    )
