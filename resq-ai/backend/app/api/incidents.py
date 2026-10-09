from datetime import datetime
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import Event
from app.models.incident import Incident, IncidentEvent, IncidentStatus
from app.schemas.incident import (
    IncidentResponse,
    IncidentDetailResponse,
    IncidentListResponse,
    ProcessEventResponse,
    BatchProcessResponse,
)
from ai.services.clustering_service import process_new_event, process_events_batch

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.post("/process-event/{event_id}", response_model=ProcessEventResponse, status_code=status.HTTP_201_CREATED)
async def process_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Process an event and assign it to an existing incident or create a new incident.

    This endpoint:
    1. Loads the event
    2. Generates embedding if not present
    3. Finds candidate nearby/recent events
    4. Calculates similarity with existing incidents
    5. Assigns to best matching incident or creates new one
    """
    # Verify event exists
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id {event_id} not found"
        )

    # Check if already processed
    existing = await db.execute(
        select(IncidentEvent).where(IncidentEvent.event_id == event_id)
    )
    if existing.scalar_one_or_none():
        # Return existing assignment
        incident_event = existing.scalar_one()
        incident_result = await db.execute(
            select(Incident).where(Incident.id == incident_event.incident_id)
        )
        incident = incident_result.scalar_one()
        return ProcessEventResponse(
            incident_id=str(incident.id),
            action="already_processed",
            relationship_score=incident_event.similarity_score or 1.0,
            incident_event_id=str(incident_event.id),
            components=incident_event.relationship_components or {},
        )

    # Process the event
    result_data = await process_new_event(event_id, db)

    return ProcessEventResponse(
        incident_id=result_data["incident_id"],
        action=result_data["action"],
        relationship_score=result_data["relationship_score"],
        incident_event_id=result_data.get("incident_event_id"),
        components=result_data["components"],
    )


@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    status: Optional[IncidentStatus] = Query(None, description="Filter by incident status"),
    incident_type: Optional[str] = Query(None, description="Filter by incident type"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (ISO format)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of incidents to return"),
    offset: int = Query(0, ge=0, description="Number of incidents to skip"),
    db: AsyncSession = Depends(get_db),
):
    """Return stored incidents with optional filters."""
    query = select(Incident)

    if status:
        query = query.where(Incident.status == status)
    if incident_type:
        query = query.where(Incident.incident_type == incident_type)
    if start_date:
        query = query.where(Incident.start_time >= start_date)
    if end_date:
        query = query.where(Incident.start_time <= end_date)

    query = query.order_by(Incident.last_updated.desc())

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Apply pagination
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    incidents = list(result.scalars().all())

    return IncidentListResponse(
        incidents=incidents,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{incident_id}", response_model=IncidentDetailResponse)
async def get_incident(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Return incident information with related events.

    Includes:
    - Incident details
    - All related events with relationship scores
    """
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with id {incident_id} not found"
        )

    # Get related events with relationship details
    events_result = await db.execute(
        select(IncidentEvent).where(IncidentEvent.incident_id == incident_id)
    )
    incident_events = list(events_result.scalars().all())

    return IncidentDetailResponse(
        **incident.__dict__,
        events=incident_events,
    )


@router.get("/{incident_id}/events", response_model=IncidentListResponse)
async def get_incident_events(
    incident_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Return all events belonging to an incident."""
    # Verify incident exists
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with id {incident_id} not found"
        )

    # Get events
    events_query = (
        select(Event)
        .join(IncidentEvent, Event.id == IncidentEvent.event_id)
        .where(IncidentEvent.incident_id == incident_id)
        .order_by(Event.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )

    count_query = (
        select(func.count())
        .select_from(
            select(Event.id)
            .join(IncidentEvent, Event.id == IncidentEvent.event_id)
            .where(IncidentEvent.incident_id == incident_id)
        )
    )

    events_result = await db.execute(events_query)
    events = list(events_result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return IncidentListResponse(
        incidents=events,  # Reusing schema, but it's events here
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/batch-process", response_model=BatchProcessResponse)
async def batch_process_events(
    event_ids: Optional[List[str]] = None,
    limit: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Batch process events for incident clustering.

    Args:
        event_ids: Optional list of event UUIDs to process
        limit: Optional limit on number of events to process

    Returns:
        Summary of processing results
    """
    # Convert string IDs to UUIDs if provided
    uuid_ids = None
    if event_ids:
        try:
            uuid_ids = [UUID(eid) for eid in event_ids]
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid event ID format: {e}"
            )

    result = await process_events_batch(db, event_ids=uuid_ids, limit=limit)

    return BatchProcessResponse(**result)