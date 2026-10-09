import logging
from datetime import datetime
from typing import Optional, List, Tuple
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ai.config import ai_config
from ai.services.embedding_service import generate_event_embedding
from ai.services.similarity_service import (
    find_candidate_events,
    calculate_event_incident_similarity,
    calculate_event_event_similarity,
    RelationshipScore,
)
from app.models.event import Event
from app.models.incident import Incident, IncidentEvent, IncidentStatus
from app.models.event_analysis import EventAIAnalysis

logger = logging.getLogger(__name__)


async def get_latest_ai_analysis(event_id: UUID, db: AsyncSession) -> Optional[EventAIAnalysis]:
    """Get the most recent AI analysis for an event."""
    result = await db.execute(
        select(EventAIAnalysis)
        .where(EventAIAnalysis.event_id == event_id)
        .order_by(EventAIAnalysis.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def generate_and_store_embedding(event: Event, db: AsyncSession) -> Optional[List[float]]:
    """Generate embedding for event and store it in the event metadata."""
    ai_analysis = await get_latest_ai_analysis(event.id, db)

    embedding = generate_event_embedding(
        event_text=event.text_content,
        disaster_type=ai_analysis.disaster_type if ai_analysis else getattr(event, 'event_type', None),
        ai_summary=ai_analysis.summary if ai_analysis else None,
        location_mentions=ai_analysis.location_mentions if ai_analysis else None,
        damage_observed=ai_analysis.damage_observed if ai_analysis else None,
    )

    if embedding:
        # Store embedding in event metadata
        if event.metadata is None:
            event.metadata = {}
        event.metadata['embedding'] = embedding
        await db.commit()

    return embedding


def build_incident_title(incident_type: Optional[str], location_name: Optional[str], event_count: int) -> str:
    """Generate a deterministic title for an incident."""
    type_str = incident_type or "incident"
    loc_str = f" near {location_name}" if location_name else ""
    return f"Possible {type_str}{loc_str} ({event_count} report{'s' if event_count > 1 else ''})"


def calculate_centroid(events: List[Event]) -> Tuple[Optional[float], Optional[float]]:
    """Calculate geographic centroid from a list of events."""
    valid_events = [e for e in events if e.latitude is not None and e.longitude is not None]
    if not valid_events:
        return None, None

    lat_sum = sum(e.latitude for e in valid_events)
    lon_sum = sum(e.longitude for e in valid_events)
    return lat_sum / len(valid_events), lon_sum / len(valid_events)


async def create_new_incident(
    event: Event,
    event_embedding: Optional[List[float]],
    db: AsyncSession,
) -> Incident:
    """Create a new incident from an event."""
    ai_analysis = await get_latest_ai_analysis(event.id, db)
    incident_type = ai_analysis.disaster_type if ai_analysis else getattr(event, 'event_type', None)

    incident = Incident(
        incident_type=incident_type,
        title=build_incident_title(incident_type, event.location_name, 1),
        summary=event.text_content or ai_analysis.summary if ai_analysis else event.text_content,
        centroid_latitude=event.latitude,
        centroid_longitude=event.longitude,
        start_time=event.timestamp,
        last_updated=event.timestamp,
        event_count=1,
        status=IncidentStatus.EMERGING,
        confidence=ai_analysis.disaster_type_confidence if ai_analysis else None,
    )

    db.add(incident)
    await db.flush()

    # Create incident-event relationship
    incident_event = IncidentEvent(
        incident_id=incident.id,
        event_id=event.id,
        similarity_score=1.0,  # Perfect match with itself
        geographic_distance_meters=0.0,
        temporal_distance_minutes=0.0,
        disaster_type_match={"event_type": incident_type, "incident_type": incident_type},
        assignment_confidence=1.0,
        relationship_components={
            "semantic_similarity": 1.0,
            "geographic_score": 1.0,
            "temporal_score": 1.0,
            "disaster_type_score": 1.0,
        },
    )
    db.add(incident_event)

    await db.commit()
    await db.refresh(incident)

    logger.info(f"Created new incident {incident.id} for event {event.id}")
    return incident


async def add_event_to_incident(
    event: Event,
    incident: Incident,
    relationship_score: RelationshipScore,
    event_embedding: Optional[List[float]],
    db: AsyncSession,
) -> IncidentEvent:
    """Add an event to an existing incident and update incident statistics."""
    # Create incident-event relationship
    incident_event = IncidentEvent(
        incident_id=incident.id,
        event_id=event.id,
        similarity_score=relationship_score.overall_score,
        geographic_distance_meters=relationship_score.components.geographic_distance_meters,
        temporal_distance_minutes=relationship_score.components.temporal_distance_minutes,
        disaster_type_match={
            "event_type": getattr(event, 'event_type', None),
            "incident_type": incident.incident_type,
            "match": relationship_score.components.disaster_type_match,
        },
        assignment_confidence=relationship_score.overall_score,
        relationship_components=relationship_score.components.to_dict(),
    )
    db.add(incident_event)

    # Update incident
    incident.event_count += 1
    incident.last_updated = max(incident.last_updated, event.timestamp)
    incident.start_time = min(incident.start_time, event.timestamp)

    # Recalculate centroid
    all_events = await db.execute(
        select(Event).join(IncidentEvent).where(IncidentEvent.incident_id == incident.id)
    )
    events = list(all_events.scalars().all())
    centroid_lat, centroid_lon = calculate_centroid(events)
    incident.centroid_latitude = centroid_lat
    incident.centroid_longitude = centroid_lon

    # Update status if multiple events
    if incident.event_count >= 3:
        incident.status = IncidentStatus.ACTIVE
    elif incident.event_count >= 2:
        incident.status = IncidentStatus.ACTIVE

    # Update confidence
    if relationship_score.overall_score > (incident.confidence or 0):
        incident.confidence = relationship_score.overall_score

    # Update summary if new information
    if event.text_content and event.text_content not in (incident.summary or ""):
        incident.summary = (incident.summary or "") + " | " + event.text_content[:500]

    incident.title = build_incident_title(incident.incident_type, event.location_name, incident.event_count)

    await db.commit()
    await db.refresh(incident)

    logger.info(f"Added event {event.id} to incident {incident.id} (score: {relationship_score.overall_score:.2f})")
    return incident_event


async def find_best_matching_incident(
    event: Event,
    event_embedding: Optional[List[float]],
    db: AsyncSession,
) -> Tuple[Optional[Incident], Optional[RelationshipScore]]:
    """
    Find the best matching incident for an event.

    Returns (incident, relationship_score) or (None, None) if no match.
    """
    # First, find candidate events from existing incidents
    candidate_events = await find_candidate_events(event, db)

    if not candidate_events:
        return None, None

    # Get unique incidents from candidate events
    incident_ids = set()
    for ce in candidate_events:
        result = await db.execute(
            select(IncidentEvent.incident_id).where(IncidentEvent.event_id == ce.id)
        )
        incident_ids.update([row[0] for row in result.fetchall()])

    if not incident_ids:
        return None, None

    # Evaluate each incident
    best_incident = None
    best_score = None
    best_relationship = None

    for incident_id in incident_ids:
        incident_result = await db.execute(
            select(Incident).where(Incident.id == incident_id)
        )
        incident = incident_result.scalar_one_or_none()
        if not incident:
            continue

        # Calculate similarity with incident
        relationship = await calculate_event_incident_similarity(
            event, incident, event_embedding, db
        )

        if relationship and relationship.overall_score >= ai_config.RELATIONSHIP_SCORE_THRESHOLD:
            if best_score is None or relationship.overall_score > best_score:
                best_score = relationship.overall_score
                best_incident = incident
                best_relationship = relationship

    return best_incident, best_relationship


async def process_new_event(event_id: UUID, db: AsyncSession) -> dict:
    """
    Process a new event and assign to incident or create new one.

    Returns result dictionary with incident info and assignment details.
    """
    # Load event
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise ValueError(f"Event {event_id} not found")

    # Generate/store embedding
    event_embedding = None
    if event.metadata and 'embedding' in event.metadata:
        event_embedding = event.metadata['embedding']
    else:
        event_embedding = await generate_and_store_embedding(event, db)

    # Find best matching incident
    incident, relationship = await find_best_matching_incident(event, event_embedding, db)

    if incident:
        # Add to existing incident
        incident_event = await add_event_to_incident(event, incident, relationship, event_embedding, db)
        return {
            "incident_id": str(incident.id),
            "action": "added_to_existing",
            "relationship_score": relationship.overall_score,
            "incident_event_id": str(incident_event.id),
            "components": relationship.components.to_dict(),
        }
    else:
        # Create new incident
        new_incident = await create_new_incident(event, event_embedding, db)
        return {
            "incident_id": str(new_incident.id),
            "action": "created_new",
            "relationship_score": 1.0,
            "components": {
                "semantic_similarity": 1.0,
                "geographic_score": 1.0,
                "temporal_score": 1.0,
                "disaster_type_score": 1.0,
            },
        }


async def process_events_batch(
    db: AsyncSession,
    event_ids: Optional[List[UUID]] = None,
    limit: Optional[int] = None,
) -> dict:
    """
    Batch process events for incident clustering.

    If event_ids provided, process those. Otherwise, process unprocessed events.
    """
    query = select(Event).order_by(Event.timestamp)

    if event_ids:
        query = query.where(Event.id.in_(event_ids))
    elif limit:
        query = query.limit(limit)

    result = await db.execute(query)
    events = list(result.scalars().all())

    processed = 0
    new_incidents = 0
    updated_incidents = 0
    errors = []

    for event in events:
        try:
            # Check if already processed
            existing = await db.execute(
                select(IncidentEvent).where(IncidentEvent.event_id == event.id)
            )
            if existing.scalar_one_or_none():
                continue  # Already assigned

            result = await process_new_event(event.id, db)
            processed += 1

            if result["action"] == "created_new":
                new_incidents += 1
            else:
                updated_incidents += 1

        except Exception as e:
            logger.error(f"Failed to process event {event.id}: {e}")
            errors.append({"event_id": str(event.id), "error": str(e)})

    return {
        "processed_events": processed,
        "new_incidents": new_incidents,
        "updated_incidents": updated_incidents,
        "errors": errors,
    }