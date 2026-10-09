from datetime import datetime
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.event import Event
from app.models.event_analysis import EventAIAnalysis
from app.schemas.analysis import DisasterAnalysis, EventAnalysisResponse, AnalyzeEventRequest
from ai.services.multimodal_analyzer import EventAnalyzer
from ai.models import model_manager

router = APIRouter(prefix="/events", tags=["analysis"])


def get_modality_text(analysis: DisasterAnalysis, text: Optional[str], image_path: Optional[str], video_path: Optional[str]) -> str:
    """Determine which modalities were used."""
    modalities = []
    if text:
        modalities.append("text")
    if image_path:
        modalities.append("image")
    if video_path:
        modalities.append("video")
    return ", ".join(modalities) if modalities else "none"


@router.post("/{event_id}/analyze", response_model=EventAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def analyze_event(
    event_id: UUID,
    request: AnalyzeEventRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Run multimodal AI analysis for an existing event.

    The analysis uses available text, image, and video content from the event
    and any additional content provided in the request.
    """
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id {event_id} not found"
        )

    text = request.text or event.text_content
    image_path = request.image_path or event.image_url
    video_path = request.video_path or event.video_url

    if not text and not image_path and not video_path:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Event has no analyzable content (no text, image, or video)"
        )

    analyzer = EventAnalyzer()
    analysis = analyzer.analyze_event(
        event,
        text=text,
        image_path=image_path,
        video_path=video_path,
    )

    modality = get_modality_text(analysis, text, image_path, video_path)
    model_name = model_manager.get_model().model_name

    db_analysis = EventAIAnalysis(
        event_id=event_id,
        modality=modality,
        disaster_type=analysis.disaster_type,
        disaster_type_confidence=analysis.disaster_type_confidence,
        severity_indicators=analysis.severity_indicators,
        location_mentions=analysis.location_mentions,
        damage_observed=analysis.damage_observed,
        people_affected=analysis.people_affected,
        vehicles_observed=analysis.vehicles_observed,
        infrastructure_damage=analysis.infrastructure_damage,
        environmental_conditions=analysis.environmental_conditions,
        summary=analysis.summary,
        evidence_description=analysis.evidence_description,
        model_name=model_name,
    )

    db.add(db_analysis)
    await db.commit()
    await db.refresh(db_analysis)

    return EventAnalysisResponse(
        id=db_analysis.id,
        event_id=db_analysis.event_id,
        modality=db_analysis.modality,
        analysis=analysis,
        model_name=db_analysis.model_name,
        created_at=db_analysis.created_at,
    )


@router.get("/{event_id}/analysis", response_model=EventAnalysisResponse)
async def get_event_analysis(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the latest AI analysis for an event.

    Does NOT automatically run analysis - only returns stored results.
    """
    result = await db.execute(
        select(EventAIAnalysis)
        .where(EventAIAnalysis.event_id == event_id)
        .order_by(EventAIAnalysis.created_at.desc())
    )
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analysis found for event {event_id}. Run POST /events/{event_id}/analyze first."
        )

    disaster_analysis = DisasterAnalysis(
        disaster_type=analysis.disaster_type,
        disaster_type_confidence=analysis.disaster_type_confidence,
        severity_indicators=analysis.severity_indicators or [],
        location_mentions=analysis.location_mentions or [],
        damage_observed=analysis.damage_observed or [],
        people_affected=analysis.people_affected,
        vehicles_observed=analysis.vehicles_observed or [],
        infrastructure_damage=analysis.infrastructure_damage or [],
        environmental_conditions=analysis.environmental_conditions or [],
        summary=analysis.summary or "",
        evidence_description=analysis.evidence_description or "",
    )

    return EventAnalysisResponse(
        id=analysis.id,
        event_id=analysis.event_id,
        modality=analysis.modality,
        analysis=disaster_analysis,
        model_name=analysis.model_name,
        created_at=analysis.created_at,
    )