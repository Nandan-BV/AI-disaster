import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.incident import Incident, IncidentEvent
from app.models.event_analysis import EventAIAnalysis
from app.models.evidence import Evidence, EvidenceType, EvidenceRole
from ai.schemas.analysis import DisasterAnalysis

logger = logging.getLogger(__name__)


@dataclass
class CollectedEvidence:
    """Container for collected evidence from an event."""
    event_id: UUID
    incident_id: Optional[UUID] = None
    event_text: Optional[str] = None
    event_source: Optional[str] = None
    event_timestamp: Optional[datetime] = None
    event_location: Optional[tuple] = None  # (lat, lon)
    event_location_name: Optional[str] = None
    ai_analysis: Optional[DisasterAnalysis] = None
    incident_event: Optional[IncidentEvent] = None  # Phase 3 relationship data
    image_analysis: Optional[DisasterAnalysis] = None
    video_analysis: Optional[DisasterAnalysis] = None


@dataclass
class IncidentEvidenceCollection:
    """Complete evidence collection for an incident."""
    incident_id: UUID
    incident: Incident
    events: List[CollectedEvidence] = field(default_factory=list)
    total_events: int = 0
    unique_sources: List[str] = field(default_factory=list)
    time_range: Optional[tuple] = None  # (start, end)
    geographic_bounds: Optional[Dict] = None


async def collect_incident_evidence(incident_id: UUID, db: AsyncSession) -> IncidentEvidenceCollection:
    """
    Collect all evidence associated with an incident from its related events.
    """
    # Get incident
    incident_result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = incident_result.scalar_one_or_none()
    if not incident:
        raise ValueError(f"Incident {incident_id} not found")

    # Get all events for this incident with their relationship data
    events_result = await db.execute(
        select(Event, IncidentEvent)
        .join(IncidentEvent, Event.id == IncidentEvent.event_id)
        .where(IncidentEvent.incident_id == incident_id)
        .order_by(Event.timestamp)
    )
    event_relationships = list(events_result.all())

    # Collect evidence from each event
    collected_events = []
    sources = set()
    timestamps = []

    for event, incident_event in event_relationships:
        # Get latest AI analysis for this event
        ai_analysis_result = await db.execute(
            select(EventAIAnalysis)
            .where(EventAIAnalysis.event_id == event.id)
            .order_by(EventAIAnalysis.created_at.desc())
            .limit(1)
        )
        ai_analysis = ai_analysis_result.scalar_one_or_none()

        # Convert AI analysis to DisasterAnalysis if present
        disaster_analysis = None
        if ai_analysis:
            disaster_analysis = DisasterAnalysis(
                disaster_type=ai_analysis.disaster_type,
                disaster_type_confidence=ai_analysis.disaster_type_confidence,
                severity_indicators=ai_analysis.severity_indicators or [],
                location_mentions=ai_analysis.location_mentions or [],
                damage_observed=ai_analysis.damage_observed or [],
                people_affected=ai_analysis.people_affected,
                vehicles_observed=ai_analysis.vehicles_observed or [],
                infrastructure_damage=ai_analysis.infrastructure_damage or [],
                environmental_conditions=ai_analysis.environmental_conditions or [],
                summary=ai_analysis.summary or "",
                evidence_description=ai_analysis.evidence_description or "",
            )

        if event.source:
            sources.add(event.source)
        timestamps.append(event.timestamp)

        collected = CollectedEvidence(
            event_id=event.id,
            incident_id=incident_id,
            event_text=event.text_content,
            event_source=event.source,
            event_timestamp=event.timestamp,
            event_location=(event.latitude, event.longitude),
            event_location_name=event.location_name,
            ai_analysis=disaster_analysis,
            incident_event=incident_event,
        )
        collected_events.append(collected)

    # Calculate time range
    time_range = None
    if timestamps:
        time_range = (min(timestamps), max(timestamps))

    # Calculate geographic bounds
    geographic_bounds = None
    lats = [e.event_location[0] for e in collected_events if e.event_location]
    lons = [e.event_location[1] for e in collected_events if e.event_location]
    if lats and lons:
        geographic_bounds = {
            "min_lat": min(lats),
            "max_lat": max(lats),
            "min_lon": min(lons),
            "max_lon": max(lons),
            "centroid_lat": sum(lats) / len(lats),
            "centroid_lon": sum(lons) / len(lons),
        }

    return IncidentEvidenceCollection(
        incident_id=incident_id,
        incident=incident,
        events=collected_events,
        total_events=len(collected_events),
        unique_sources=list(sources),
        time_range=time_range,
        geographic_bounds=geographic_bounds,
    )


def extract_text_evidence(evidence: CollectedEvidence) -> List[Evidence]:
    """Extract text-based evidence from an event."""
    items = []

    if evidence.event_text and evidence.event_text.strip():
        # Analyze the text content for evidence quality
        text = evidence.event_text.strip()

        # Determine role based on content
        role = determine_text_role(text, evidence.ai_analysis)

        # Quality based on directness and specificity
        quality = calculate_text_quality(text, evidence.ai_analysis)

        items.append(Evidence(
            incident_id=evidence.incident_id,
            event_id=evidence.event_id,
            evidence_type=EvidenceType.TEXT,
            evidence_role=role,
            description=f"Text report: {text[:500]}",
            evidence_quality=quality,
            confidence=quality * 0.8,  # Text is generally less certain than visual
            source=evidence.event_source,
            metadata={
                "full_text": text,
                "disaster_type": evidence.ai_analysis.disaster_type if evidence.ai_analysis else None,
            },
        ))

    return items


def extract_image_evidence(evidence: CollectedEvidence) -> List[Evidence]:
    """Extract image-based evidence from event's AI analysis."""
    items = []

    if evidence.ai_analysis and evidence.ai_analysis.evidence_description:
        # Check if image analysis was performed
        modality = evidence.ai_analysis.evidence_description.lower()
        if "image" in modality or "visual" in modality:
            role = determine_visual_role(evidence.ai_analysis)
            quality = calculate_visual_quality(evidence.ai_analysis)

            items.append(Evidence(
                incident_id=evidence.incident_id,
                event_id=evidence.event_id,
                evidence_type=EvidenceType.IMAGE,
                evidence_role=role,
                description=f"Image analysis: {evidence.ai_analysis.summary}",
                evidence_quality=quality,
                confidence=quality * 0.9,  # Visual evidence is generally stronger
                source=evidence.event_source,
                metadata={
                    "disaster_type": evidence.ai_analysis.disaster_type,
                    "damage_observed": evidence.ai_analysis.damage_observed,
                    "modality": "image",
                },
            ))

    return items


def extract_video_evidence(evidence: CollectedEvidence) -> List[Evidence]:
    """Extract video-based evidence from event's AI analysis."""
    items = []

    if evidence.ai_analysis and evidence.ai_analysis.evidence_description:
        modality = evidence.ai_analysis.evidence_description.lower()
        if "video" in modality or "frame" in modality:
            role = determine_visual_role(evidence.ai_analysis)
            quality = calculate_visual_quality(evidence.ai_analysis)

            items.append(Evidence(
                incident_id=evidence.incident_id,
                event_id=evidence.event_id,
                evidence_type=EvidenceType.VIDEO,
                evidence_role=role,
                description=f"Video analysis: {evidence.ai_analysis.summary}",
                evidence_quality=quality,
                confidence=quality * 0.9,
                source=evidence.event_source,
                metadata={
                    "disaster_type": evidence.ai_analysis.disaster_type,
                    "damage_observed": evidence.ai_analysis.damage_observed,
                    "modality": "video",
                    "frame_count": evidence.ai_analysis.evidence_description,
                },
            ))

    return items


def extract_geographic_evidence(
    collection: IncidentEvidenceCollection,
    incident_center: Optional[tuple] = None
) -> List[Evidence]:
    """Extract geographic consistency evidence."""
    items = []

    if not collection.geographic_bounds or not incident_center:
        return items

    incident_lat, incident_lon = incident_center

    # Analyze each event's geographic consistency
    distances = []
    for event in collection.events:
        if event.event_location:
            lat, lon = event.event_location
            dist = haversine_distance(incident_lat, incident_lon, lat, lon)
            distances.append(dist)

    if not distances:
        return items

    avg_distance = sum(distances) / len(distances)
    max_distance = max(distances)

    # Consistency score based on distances
    if avg_distance < 1000:  # Within 1km
        consistency = 1.0 - (avg_distance / 2000)
        role = EvidenceRole.SUPPORTING
    elif avg_distance < 5000:  # Within 5km
        consistency = 1.0 - (avg_distance / 10000)
        role = EvidenceRole.SUPPORTING
    else:
        consistency = 0.2
        role = EvidenceRole.NEUTRAL

    items.append(Evidence(
        incident_id=collection.incident_id,
        event_id=None,
        evidence_type=EvidenceType.GEOGRAPHIC,
        evidence_role=role,
        description=f"Geographic consistency: {len(distances)} events, avg distance {avg_distance:.0f}m from incident center",
        evidence_quality=consistency,
        confidence=consistency,
        source="phase3_clustering",
        metadata={
            "event_count": len(distances),
            "avg_distance_meters": avg_distance,
            "max_distance_meters": max_distance,
            "incident_center": incident_center,
        },
    ))

    return items


def extract_temporal_evidence(collection: IncidentEvidenceCollection) -> List[Evidence]:
    """Extract temporal consistency evidence."""
    items = []

    if not collection.time_range:
        return items

    start, end = collection.time_range
    duration_minutes = (end - start).total_seconds() / 60
    event_count = collection.total_events

    if event_count < 2:
        items.append(Evidence(
            incident_id=collection.incident_id,
            event_id=None,
            evidence_type=EvidenceType.TEMPORAL,
            evidence_role=EvidenceRole.NEUTRAL,
            description=f"Single event, no temporal pattern to evaluate",
            evidence_quality=0.3,
            confidence=0.3,
            source="phase3_clustering",
            metadata={"event_count": event_count},
        ))
        return items

    # Temporal consistency based on duration and event count
    if duration_minutes < 60 and event_count >= 3:
        consistency = 0.9
        role = EvidenceRole.SUPPORTING
        desc = f"Tight temporal cluster: {event_count} events within {duration_minutes:.0f} minutes"
    elif duration_minutes < 240:  # 4 hours
        consistency = 0.7
        role = EvidenceRole.SUPPORTING
        desc = f"Moderate temporal cluster: {event_count} events over {duration_minutes:.0f} minutes"
    elif duration_minutes < 1440:  # 24 hours
        consistency = 0.5
        role = EvidenceRole.NEUTRAL
        desc = f"Extended temporal spread: {event_count} events over {duration_minutes:.0f} minutes"
    else:
        consistency = 0.2
        role = EvidenceRole.CONTRADICTING
        desc = f"Wide temporal spread: {event_count} events over {duration_minutes:.0f} minutes"

    items.append(Evidence(
        incident_id=collection.incident_id,
        event_id=None,
        evidence_type=EvidenceType.TEMPORAL,
        evidence_role=role,
        description=desc,
        evidence_quality=consistency,
        confidence=consistency,
        source="phase3_clustering",
        metadata={
            "event_count": event_count,
            "duration_minutes": duration_minutes,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        },
    ))

    return items


def extract_multimodal_consistency(collection: IncidentEvidenceCollection) -> List[Evidence]:
    """Extract multimodal consistency evidence."""
    items = []

    modalities_per_event = []
    for event in collection.events:
        modalities = set()
        if event.event_text:
            modalities.add("text")
        if event.ai_analysis and event.ai_analysis.evidence_description:
            desc = event.ai_analysis.evidence_description.lower()
            if "image" in desc:
                modalities.add("image")
            if "video" in desc or "frame" in desc:
                modalities.add("video")
        if modalities:
            modalities_per_event.append(modalities)

    if not modalities_per_event:
        return items

    # Check cross-modal agreement on disaster type
    disaster_types = []
    for event in collection.events:
        if event.ai_analysis and event.ai_analysis.disaster_type:
            disaster_types.append(event.ai_analysis.disaster_type)

    if not disaster_types:
        return items

    # Consistency of disaster type across modalities
    from collections import Counter
    type_counts = Counter(disaster_types)
    most_common_type, most_common_count = type_counts.most_common(1)[0]
    type_consistency = most_common_count / len(disaster_types)

    # Multimodal events (events with multiple modalities)
    multimodal_events = sum(1 for m in modalities_per_event if len(m) > 1)

    # Overall multimodal consistency
    if type_consistency > 0.8 and multimodal_events > 0:
        consistency = 0.9
        role = EvidenceRole.SUPPORTING
        desc = f"Strong multimodal agreement: {type_consistency:.0%} disaster type consistency, {multimodal_events} multimodal events"
    elif type_consistency > 0.6:
        consistency = 0.7
        role = EvidenceRole.SUPPORTING
        desc = f"Moderate multimodal agreement: {type_consistency:.0%} disaster type consistency"
    elif type_consistency > 0.4:
        consistency = 0.5
        role = EvidenceRole.NEUTRAL
        desc = f"Mixed multimodal signals: {type_consistency:.0%} disaster type consistency"
    else:
        consistency = 0.3
        role = EvidenceRole.CONTRADICTING
        desc = f"Low multimodal agreement: {type_consistency:.0%} disaster type consistency"

    items.append(Evidence(
        incident_id=collection.incident_id,
        event_id=None,
        evidence_type=EvidenceType.MULTIMODAL,
        evidence_role=role,
        description=desc,
        evidence_quality=consistency,
        confidence=consistency * 0.8,
        source="phase2_analysis",
        metadata={
            "disaster_types": dict(type_counts),
            "type_consistency": type_consistency,
            "multimodal_events": multimodal_events,
            "total_events_with_modalities": len(modalities_per_event),
        },
    ))

    return items


def extract_source_diversity(collection: IncidentEvidenceCollection) -> List[Evidence]:
    """Extract source diversity evidence."""
    items = []

    if not collection.unique_sources:
        return items

    source_count = len(collection.unique_sources)
    event_count = collection.total_events

    # Calculate diversity score
    if source_count >= 4:
        diversity = 0.9
        role = EvidenceRole.SUPPORTING
        desc = f"High source diversity: {source_count} independent source types across {event_count} events"
    elif source_count >= 2:
        diversity = 0.6
        role = EvidenceRole.SUPPORTING
        desc = f"Moderate source diversity: {source_count} source types across {event_count} events"
    elif source_count == 1 and event_count > 1:
        diversity = 0.3
        role = EvidenceRole.NEUTRAL
        desc = f"Single source type: all {event_count} events from '{collection.unique_sources[0]}'"
    else:
        diversity = 0.2
        role = EvidenceRole.NEUTRAL
        desc = f"Single source: 1 event from '{collection.unique_sources[0]}'"

    items.append(Evidence(
        incident_id=collection.incident_id,
        event_id=None,
        evidence_type=EvidenceType.SOURCE_DIVERSITY,
        evidence_role=role,
        description=desc,
        evidence_quality=diversity,
        confidence=diversity,
        source="phase1_ingestion",
        metadata={
            "source_types": collection.unique_sources,
            "source_count": source_count,
            "event_count": event_count,
        },
    ))

    return items


def determine_text_role(text: str, ai_analysis: Optional[DisasterAnalysis]) -> EvidenceRole:
    """Determine if text evidence is supporting, contradicting, neutral, or uncertain."""
    text_lower = text.lower()

    # Uncertainty indicators
    uncertain_keywords = [
        "may be", "might be", "possible", "unconfirmed", "rumor", "heard",
        "someone said", "allegedly", "reportedly", "unverified", "not sure"
    ]

    # Contradicting indicators
    contradicting_keywords = [
        "not flooded", "no flood", "clear road", "normal conditions",
        "false alarm", "fake", "not true", "did not happen"
    ]

    # Supporting indicators
    supporting_keywords = [
        "confirmed", "verified", "witnessed", "saw", "observed",
        "water covering", "visible", "evacuation", "rescue", "emergency"
    ]

    for kw in contradicting_keywords:
        if kw in text_lower:
            return EvidenceRole.CONTRADICTING

    for kw in uncertain_keywords:
        if kw in text_lower:
            return EvidenceRole.UNCERTAIN

    for kw in supporting_keywords:
        if kw in text_lower:
            return EvidenceRole.SUPPORTING

    # Default based on AI analysis
    if ai_analysis and ai_analysis.disaster_type:
        return EvidenceRole.SUPPORTING

    return EvidenceRole.NEUTRAL


def calculate_text_quality(text: str, ai_analysis: Optional[DisasterAnalysis]) -> float:
    """Calculate text evidence quality (0-1)."""
    quality = 0.3  # Base quality

    # Length bonus
    if len(text) > 100:
        quality += 0.1
    elif len(text) > 50:
        quality += 0.05

    # Specificity bonus
    specific_keywords = [
        "street", "road", "building", "river", "bridge", "highway",
        "north", "south", "east", "west", "near", "intersection"
    ]
    for kw in specific_keywords:
        if kw in text.lower():
            quality += 0.05
            break

    # AI analysis confirmation
    if ai_analysis and ai_analysis.disaster_type_confidence and ai_analysis.disaster_type_confidence > 0.7:
        quality += 0.15

    return min(quality, 1.0)


def determine_visual_role(ai_analysis: DisasterAnalysis) -> EvidenceRole:
    """Determine if visual evidence is supporting, contradicting, or uncertain."""
    if not ai_analysis.disaster_type:
        return EvidenceRole.NEUTRAL

    confidence = ai_analysis.disaster_type_confidence or 0.0

    if confidence > 0.8:
        return EvidenceRole.SUPPORTING
    elif confidence > 0.5:
        return EvidenceRole.SUPPORTING
    else:
        return EvidenceRole.UNCERTAIN


def calculate_visual_quality(ai_analysis: DisasterAnalysis) -> float:
    """Calculate visual evidence quality (0-1)."""
    quality = 0.3  # Base quality

    confidence = ai_analysis.disaster_type_confidence or 0.0
    if confidence > 0.7:
        quality += 0.25
    elif confidence > 0.4:
        quality += 0.1

    # Damage observations
    if ai_analysis.damage_observed:
        quality += min(len(ai_analysis.damage_observed) * 0.05, 0.15)

    # Severity indicators
    if ai_analysis.severity_indicators:
        quality += min(len(ai_analysis.severity_indicators) * 0.03, 0.1)

    return min(quality, 1.0)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate haversine distance in meters."""
    import math
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c