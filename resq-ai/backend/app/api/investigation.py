from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.incident import Incident
from app.models.evidence import Evidence, IncidentInvestigation, EvidenceType, EvidenceRole
from app.schemas.evidence import (
    EvidenceInvestigation,
    EvidenceItem,
    EvidenceListResponse,
    IncidentInvestigationResponse,
    InvestigateRequest,
)
from ai.services.evidence_investigator import (
    investigate_incident,
    get_incident_investigation,
    get_incident_evidence,
)

router = APIRouter(prefix="/incidents", tags=["investigation"])


@router.post("/{incident_id}/investigate", response_model=IncidentInvestigationResponse, status_code=status.HTTP_201_CREATED)
async def run_investigation(
    incident_id: UUID,
    request: InvestigateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Run evidence investigation for an incident.

    This endpoint:
    1. Collects all evidence from related events
    2. Analyzes text, image, video, geographic, temporal, multimodal consistency, and source diversity
    3. Runs AI evidence investigation
    4. Stores and returns the investigation report
    """
    # Verify incident exists
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with id {incident_id} not found"
        )

    # Run investigation
    investigation = await investigate_incident(incident_id, db, force_rerun=request.force_rerun)

    return IncidentInvestigationResponse(
        **investigation.__dict__
    )


@router.get("/{incident_id}/investigation", response_model=IncidentInvestigationResponse)
async def get_investigation(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the latest evidence investigation for an incident.

    Does NOT automatically run investigation - only returns stored results.
    """
    investigation = await get_incident_investigation(incident_id, db)

    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No investigation found for incident {incident_id}. Run POST /incidents/{incident_id}/investigate first."
        )

    return IncidentInvestigationResponse(
        **investigation.__dict__
    )


@router.get("/{incident_id}/evidence", response_model=EvidenceListResponse)
async def get_evidence(
    incident_id: UUID,
    evidence_type: Optional[EvidenceType] = Query(None, description="Filter by evidence type"),
    evidence_role: Optional[EvidenceRole] = Query(None, description="Filter by evidence role"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of evidence items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve all evidence items associated with an incident.

    Supports filtering by evidence type and role.
    """
    # Verify incident exists
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with id {incident_id} not found"
        )

    evidence_items = await get_incident_evidence(
        incident_id, db,
        evidence_type=evidence_type,
        evidence_role=evidence_role,
        limit=limit,
        offset=offset,
    )

    # Get total count
    count_query = select(func.count()).select_from(
        select(Evidence.id).where(Evidence.incident_id == incident_id)
    )
    if evidence_type:
        count_query = count_query.where(Evidence.evidence_type == evidence_type)
    if evidence_role:
        count_query = count_query.where(Evidence.evidence_role == evidence_role)

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return EvidenceListResponse(
        evidence=[EvidenceItem(**ev.__dict__) for ev in evidence_items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{incident_id}/investigation-summary", response_model=EvidenceInvestigation)
async def get_investigation_summary(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a detailed investigation summary with categorized evidence.

    This provides the full structured investigation output including
    supporting, contradicting, neutral, and uncertain evidence.
    """
    investigation = await get_incident_investigation(incident_id, db)

    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No investigation found for incident {incident_id}. Run POST /incidents/{incident_id}/investigate first."
        )

    # Get all evidence items
    all_evidence = await get_incident_evidence(incident_id, db, limit=200)

    # Categorize
    supporting = [e for e in all_evidence if e.evidence_role == EvidenceRole.SUPPORTING]
    contradicting = [e for e in all_evidence if e.evidence_role == EvidenceRole.CONTRADICTING]
    neutral = [e for e in all_evidence if e.evidence_role == EvidenceRole.NEUTRAL]
    uncertain = [e for e in all_evidence if e.evidence_role == EvidenceRole.UNCERTAIN]

    # Get incident for location info
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one()

    return EvidenceInvestigation(
        incident_id=incident_id,
        supporting_evidence=[EvidenceItem(**e.__dict__) for e in supporting],
        contradicting_evidence=[EvidenceItem(**e.__dict__) for e in contradicting],
        neutral_evidence=[EvidenceItem(**e.__dict__) for e in neutral],
        uncertain_evidence=[EvidenceItem(**e.__dict__) for e in uncertain],
        source_diversity=investigation.source_diversity,
        geographic_consistency=investigation.geographic_consistency,
        temporal_consistency=investigation.temporal_consistency,
        multimodal_consistency=investigation.multimodal_consistency,
        evidence_confidence_score=investigation.evidence_confidence,
        assessment=investigation.assessment,
        explanation=investigation.explanation or "",
        limitations=investigation.limitations,
        model_name=investigation.model_name,
        investigated_at=investigation.investigated_at,
    )