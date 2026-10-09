from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.incident import Incident
from app.models.risk import RiskAssessment, ImpactAssessment, RiskAssessmentHistory, RiskLevel
from app.schemas.risk import (
    RiskAssessmentResponse,
    ImpactAssessmentResponse,
    RiskHistoryResponse,
    RecalculateRiskRequest,
    RiskLevel as SchemaRiskLevel,
)
from app.services.risk_service import (
    calculate_risk_assessment,
    calculate_impact_assessment,
    recalculate_risk,
    get_latest_risk_assessment,
    get_latest_impact_assessment,
    get_risk_history,
)

router = APIRouter(prefix="/incidents", tags=["risk-impact"])


@router.post("/{incident_id}/risk-assessment", response_model=RiskAssessmentResponse, status_code=status.HTTP_201_CREATED)
async def run_risk_assessment(
    incident_id: UUID,
    request: Optional[RecalculateRiskRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Run risk and impact assessment for an incident.
    
    This endpoint:
    1. Loads the incident and related events
    2. Retrieves Phase 2 AI analysis and Phase 4 evidence investigation
    3. Calculates all risk components (severity, evidence, population, infrastructure, environment, accessibility)
    4. Computes weighted risk score and risk level
    5. Stores the assessment in the database
    """
    # Verify incident exists
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with id {incident_id} not found"
        )

    # Run risk assessment
    assessment = await calculate_risk_assessment(incident_id, db, trigger="manual")
    
    # Also calculate impact assessment
    impact = await calculate_impact_assessment(incident_id, db)
    db.add(impact)
    await db.commit()

    return RiskAssessmentResponse(
        id=assessment.id,
        incident_id=assessment.incident_id,
        risk_score=assessment.risk_score,
        risk_level=assessment.risk_level,
        severity_component=assessment.severity_component,
        evidence_component=assessment.evidence_component,
        population_component=assessment.population_component,
        infrastructure_component=assessment.infrastructure_component,
        environment_component=assessment.environment_component,
        accessibility_component=assessment.accessibility_component,
        severity_details=assessment.severity_details,
        evidence_details=assessment.evidence_details,
        population_details=assessment.population_details,
        infrastructure_details=assessment.infrastructure_details,
        environment_details=assessment.environment_details,
        accessibility_details=assessment.accessibility_details,
        explanation=assessment.explanation,
        model_name=assessment.model_name,
        assessed_at=assessment.assessed_at,
        created_at=assessment.created_at,
    )


@router.get("/{incident_id}/risk-assessment", response_model=RiskAssessmentResponse)
async def get_risk_assessment(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the latest stored risk assessment for an incident.
    
    Does NOT automatically run assessment - only returns stored results.
    """
    # Verify incident exists
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with id {incident_id} not found"
        )

    assessment = await get_latest_risk_assessment(incident_id, db)

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No risk assessment found for incident {incident_id}. Run POST /incidents/{incident_id}/risk-assessment first."
        )

    return RiskAssessmentResponse(
        id=assessment.id,
        incident_id=assessment.incident_id,
        risk_score=assessment.risk_score,
        risk_level=assessment.risk_level,
        severity_component=assessment.severity_component,
        evidence_component=assessment.evidence_component,
        population_component=assessment.population_component,
        infrastructure_component=assessment.infrastructure_component,
        environment_component=assessment.environment_component,
        accessibility_component=assessment.accessibility_component,
        severity_details=assessment.severity_details,
        evidence_details=assessment.evidence_details,
        population_details=assessment.population_details,
        infrastructure_details=assessment.infrastructure_details,
        environment_details=assessment.environment_details,
        accessibility_details=assessment.accessibility_details,
        explanation=assessment.explanation,
        model_name=assessment.model_name,
        assessed_at=assessment.assessed_at,
        created_at=assessment.created_at,
    )


@router.post("/{incident_id}/risk-assessment/recalculate", response_model=RiskAssessmentResponse, status_code=status.HTTP_201_CREATED)
async def recalculate_risk_assessment(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Recalculate risk assessment using the latest available data.
    
    This is useful when:
    - New events are added to the incident
    - New AI analysis becomes available
    - Evidence investigation is updated
    - Environmental conditions change
    """
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with id {incident_id} not found"
        )

    assessment = await recalculate_risk(incident_id, db)

    return RiskAssessmentResponse(
        id=assessment.id,
        incident_id=assessment.incident_id,
        risk_score=assessment.risk_score,
        risk_level=assessment.risk_level,
        severity_component=assessment.severity_component,
        evidence_component=assessment.evidence_component,
        population_component=assessment.population_component,
        infrastructure_component=assessment.infrastructure_component,
        environment_component=assessment.environment_component,
        accessibility_component=assessment.accessibility_component,
        severity_details=assessment.severity_details,
        evidence_details=assessment.evidence_details,
        population_details=assessment.population_details,
        infrastructure_details=assessment.infrastructure_details,
        environment_details=assessment.environment_details,
        accessibility_details=assessment.accessibility_details,
        explanation=assessment.explanation,
        model_name=assessment.model_name,
        assessed_at=assessment.assessed_at,
        created_at=assessment.created_at,
    )


@router.get("/{incident_id}/risk-history", response_model=List[RiskHistoryResponse])
async def get_risk_assessment_history(
    incident_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the risk assessment history for an incident.
    
    Shows how the risk score has changed over time.
    """
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with id {incident_id} not found"
        )

    history = await get_risk_history(incident_id, db, limit)

    return [
        RiskHistoryResponse(
            id=item.id,
            incident_id=item.incident_id,
            risk_score=item.risk_score,
            risk_level=item.risk_level,
            severity_component=item.severity_component,
            evidence_component=item.evidence_component,
            population_component=item.population_component,
            infrastructure_component=item.infrastructure_component,
            environment_component=item.environment_component,
            accessibility_component=item.accessibility_component,
            explanation=item.explanation,
            trigger=item.trigger,
            assessed_at=item.assessed_at,
        )
        for item in history
    ]


@router.get("/{incident_id}/impact", response_model=ImpactAssessmentResponse)
async def get_impact_assessment(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the latest impact assessment for an incident.
    
    Returns population exposure, infrastructure exposure, and accessibility details.
    """
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with id {incident_id} not found"
        )

    impact = await get_latest_impact_assessment(incident_id, db)

    if not impact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No impact assessment found for incident {incident_id}. Run POST /incidents/{incident_id}/risk-assessment first."
        )

    return ImpactAssessmentResponse(
        id=impact.id,
        incident_id=impact.incident_id,
        population_potentially_exposed=impact.population_potentially_exposed,
        population_zones_count=impact.population_zones_count,
        population_weighted_exposure=impact.population_weighted_exposure,
        infrastructure_potentially_exposed=impact.infrastructure_potentially_exposed,
        hospitals_count=impact.hospitals_count,
        shelters_count=impact.shelters_count,
        fire_stations_count=impact.fire_stations_count,
        police_stations_count=impact.police_stations_count,
        schools_count=impact.schools_count,
        bridges_count=impact.bridges_count,
        roads_count=impact.roads_count,
        emergency_centers_count=impact.emergency_centers_count,
        power_stations_count=impact.power_stations_count,
        water_facilities_count=impact.water_facilities_count,
        roads_potentially_affected=impact.roads_potentially_affected,
        bridges_potentially_affected=impact.bridges_potentially_affected,
        accessibility_status=impact.accessibility_status,
        accessibility_details=impact.accessibility_details,
        explanation=impact.explanation,
        assessed_at=impact.assessed_at,
        created_at=impact.created_at,
    )


@router.post("/{incident_id}/impact/recalculate", response_model=ImpactAssessmentResponse, status_code=status.HTTP_201_CREATED)
async def recalculate_impact_assessment(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Recalculate impact assessment using the latest available data.
    """
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with id {incident_id} not found"
        )

    impact = await calculate_impact_assessment(incident_id, db)
    db.add(impact)
    await db.commit()
    await db.refresh(impact)

    return ImpactAssessmentResponse(
        id=impact.id,
        incident_id=impact.incident_id,
        population_potentially_exposed=impact.population_potentially_exposed,
        population_zones_count=impact.population_zones_count,
        population_weighted_exposure=impact.population_weighted_exposure,
        infrastructure_potentially_exposed=impact.infrastructure_potentially_exposed,
        hospitals_count=impact.hospitals_count,
        shelters_count=impact.shelters_count,
        fire_stations_count=impact.fire_stations_count,
        police_stations_count=impact.police_stations_count,
        schools_count=impact.schools_count,
        bridges_count=impact.bridges_count,
        roads_count=impact.roads_count,
        emergency_centers_count=impact.emergency_centers_count,
        power_stations_count=impact.power_stations_count,
        water_facilities_count=impact.water_facilities_count,
        roads_potentially_affected=impact.roads_potentially_affected,
        bridges_potentially_affected=impact.bridges_potentially_affected,
        accessibility_status=impact.accessibility_status,
        accessibility_details=impact.accessibility_details,
        explanation=impact.explanation,
        assessed_at=impact.assessed_at,
        created_at=impact.created_at,
    )