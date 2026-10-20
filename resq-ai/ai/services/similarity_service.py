import logging
import datetime as dt
from datetime import datetime
from typing import Optional, List, Tuple
from dataclasses import dataclass

from sqlalchemy import cast, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2 import Geography
from geoalchemy2.functions import ST_Distance, ST_Transform
from geoalchemy2.shape import to_shape

from ai.config import ai_config
from ai.services.embedding_service import cosine_similarity, build_event_text_representation
from app.models.event import Event
from app.models.incident import Incident, IncidentEvent

logger = logging.getLogger(__name__)


@dataclass
class SimilarityComponents:
    """Individual similarity components for explainability."""
    semantic_similarity: float
    geographic_distance_meters: float
    temporal_distance_minutes: float
    disaster_type_match: bool
    disaster_type_score: float

    def to_dict(self) -> dict:
        return {
            "semantic_similarity": self.semantic_similarity,
            "geographic_distance_meters": self.geographic_distance_meters,
            "temporal_distance_minutes": self.temporal_distance_minutes,
            "disaster_type_match": self.disaster_type_match,
            "disaster_type_score": self.disaster_type_score,
        }


@dataclass
class RelationshipScore:
    """Complete relationship score with breakdown."""
    overall_score: float
    components: SimilarityComponents
    explanation: str

    def to_dict(self) -> dict:
        return {
            "relationship_score": self.overall_score,
            "semantic_similarity": self.components.semantic_similarity,
            "distance_meters": self.components.geographic_distance_meters,
            "time_difference_minutes": self.components.temporal_distance_minutes,
            "disaster_type_match": self.components.disaster_type_match,
            "explanation": self.explanation,
        }


async def calculate_geographic_distance(
    lat1: float, lon1: float, lat2: float, lon2: float, db: AsyncSession
) -> float:
    """Calculate geographic distance in meters between two points using PostGIS."""
    try:
        from geoalchemy2 import WKTElement

        point1 = WKTElement(f"POINT({lon1} {lat1})", srid=4326)
        point2 = WKTElement(f"POINT({lon2} {lat2})", srid=4326)

        # Use geography type for accurate distance in meters
        query = select(
            ST_Distance(
                cast(point1, Geography(srid=4326)),
                cast(point2, Geography(srid=4326)),
                use_spheroid=True,
            )
        )
        result = await db.execute(query)
        distance = result.scalar()
        return float(distance) if distance is not None else float("inf")
    except Exception as e:
        logger.warning(f"Failed to calculate geographic distance: {e}")
        # Fallback to Haversine formula
        return haversine_distance(lat1, lon1, lat2, lon2)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine formula fallback for distance calculation."""
    import math

    R = 6371000  # Earth radius in meters
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


def calculate_temporal_distance(ts1: datetime, ts2: datetime) -> float:
    """Calculate temporal distance in minutes between two timestamps."""
    diff = abs((ts1 - ts2).total_seconds())
    return diff / 60.0


def calculate_disaster_type_score(event_type: Optional[str], incident_type: Optional[str]) -> Tuple[bool, float]:
    """
    Calculate disaster type compatibility score.

    Returns: (is_match, score)
    """
    if not event_type or not incident_type:
        return False, 0.5  # Neutral if unknown

    event_type_lower = event_type.lower().strip()
    incident_type_lower = incident_type.lower().strip()

    if event_type_lower == incident_type_lower:
        return True, 1.0

    # Compatible disaster type groups
    compatible_groups = {
        "flood": ["flood", "flash_flood", "tsunami", "storm_surge"],
        "wildfire": ["wildfire", "forest_fire", "bushfire"],
        "earthquake": ["earthquake", "seismic_activity", "aftershock"],
        "landslide": ["landslide", "mudslide", "rockfall"],
        "cyclone": ["cyclone", "hurricane", "typhoon", "tropical_storm"],
        "tornado": ["tornado", "waterspout"],
        "storm": ["storm", "thunderstorm", "hail", "severe_weather"],
        "building_collapse": ["building_collapse", "structural_failure"],
        "road_blockage": ["road_blockage", "road_closure", "traffic_incident"],
    }

    for group_type, types in compatible_groups.items():
        if event_type_lower in types and incident_type_lower in types:
            return True, 0.8  # Compatible but not exact match

    # Check if both are in any group
    event_groups = {g for g, t in compatible_groups.items() if event_type_lower in t}
    incident_groups = {g for g, t in compatible_groups.items() if incident_type_lower in t}

    if event_groups & incident_groups:
        return True, 0.6  # Same category group

    return False, 0.0  # Incompatible


def calculate_geographic_score(distance_meters: float) -> float:
    """Calculate geographic proximity score (0-1)."""
    if distance_meters <= 0:
        return 1.0
    max_distance = ai_config.MAX_DISTANCE_METERS
    if distance_meters >= max_distance:
        return 0.0
    # Linear decay
    return 1.0 - (distance_meters / max_distance)


def calculate_temporal_score(time_diff_minutes: float) -> float:
    """Calculate temporal proximity score (0-1)."""
    if time_diff_minutes <= 0:
        return 1.0
    max_time = ai_config.MAX_TIME_DIFFERENCE_MINUTES
    if time_diff_minutes >= max_time:
        return 0.0
    # Linear decay
    return 1.0 - (time_diff_minutes / max_time)


def calculate_relationship_score(
    semantic_similarity: float,
    geographic_distance_meters: float,
    temporal_distance_minutes: float,
    disaster_type_match: bool,
    disaster_type_score: float,
) -> RelationshipScore:
    """Calculate overall relationship score from components."""
    geographic_score = calculate_geographic_score(geographic_distance_meters)
    temporal_score = calculate_temporal_score(temporal_distance_minutes)

    # Weighted combination
    overall = (
        ai_config.SEMANTIC_WEIGHT * semantic_similarity
        + ai_config.GEOGRAPHIC_WEIGHT * geographic_score
        + ai_config.TEMPORAL_WEIGHT * temporal_score
        + ai_config.DISASTER_TYPE_WEIGHT * disaster_type_score
    )

    components = SimilarityComponents(
        semantic_similarity=semantic_similarity,
        geographic_distance_meters=geographic_distance_meters,
        temporal_distance_minutes=temporal_distance_minutes,
        disaster_type_match=disaster_type_match,
        disaster_type_score=disaster_type_score,
    )

    explanation_parts = [
        f"Semantic similarity: {semantic_similarity:.2f} (weight: {ai_config.SEMANTIC_WEIGHT})",
        f"Geographic distance: {geographic_distance_meters:.0f}m (score: {geographic_score:.2f}, weight: {ai_config.GEOGRAPHIC_WEIGHT})",
        f"Temporal distance: {temporal_distance_minutes:.1f}min (score: {temporal_score:.2f}, weight: {ai_config.TEMPORAL_WEIGHT})",
        f"Disaster type: {'match' if disaster_type_match else 'mismatch'} (score: {disaster_type_score:.2f}, weight: {ai_config.DISASTER_TYPE_WEIGHT})",
    ]

    return RelationshipScore(
        overall_score=overall,
        components=components,
        explanation="; ".join(explanation_parts),
    )


async def find_candidate_events(
    event: Event,
    db: AsyncSession,
    max_distance: Optional[float] = None,
    max_time_minutes: Optional[int] = None,
) -> List[Event]:
    """
    Find candidate events for clustering using geographic and temporal filters.

    This avoids comparing the event against ALL events by using
    PostGIS spatial index and time index for efficient filtering.
    """
    max_distance = max_distance or ai_config.MAX_DISTANCE_METERS
    max_time_minutes = max_time_minutes or ai_config.MAX_TIME_DIFFERENCE_MINUTES

    # Time window
    time_threshold = event.timestamp - dt.timedelta(minutes=max_time_minutes)

    # Geographic filter using PostGIS
    from geoalchemy2 import WKTElement
    from sqlalchemy import and_

    event_point = WKTElement(f"POINT({event.longitude} {event.latitude})", srid=4326)

    query = select(Event).where(
        and_(
            Event.id != event.id,  # Exclude self
            Event.timestamp >= time_threshold,
            Event.timestamp <= event.timestamp + dt.timedelta(minutes=max_time_minutes),
            # Spatial filter
            func.ST_Distance(
                Event.location.cast(Geography(srid=4326)),
                cast(event_point, Geography(srid=4326)),
                use_spheroid=True,
            ) <= max_distance,
        )
    ).order_by(Event.timestamp.desc())

    result = await db.execute(query)
    return list(result.scalars().all())


async def calculate_event_incident_similarity(
    event: Event,
    incident: Incident,
    event_embedding: Optional[List[float]],
    db: AsyncSession,
) -> Optional[RelationshipScore]:
    """
    Calculate relationship score between an event and an incident.

    Uses the incident's centroid and most recent event for comparison.
    """
    if not event_embedding:
        return None

    # Get incident's representative embedding (could be centroid embedding)
    # For now, use the incident's type and latest event
    incident_type = incident.incident_type
    incident_lat = incident.centroid_latitude
    incident_lon = incident.centroid_longitude

    if incident_lat is None or incident_lon is None:
        # Fallback to first event's location
        first_event = await db.execute(
            select(Event).join(IncidentEvent).where(IncidentEvent.incident_id == incident.id).limit(1)
        )
        first_event = first_event.scalar_one_or_none()
        if first_event:
            incident_lat = first_event.latitude
            incident_lon = first_event.longitude

    if incident_lat is None or incident_lon is None:
        return None

    # Calculate components
    # Note: We don't have incident embedding stored, so we use a proxy
    # In a more advanced version, we'd store incident embeddings

    # Geographic distance
    distance = await calculate_geographic_distance(
        event.latitude, event.longitude, incident_lat, incident_lon, db
    )

    # Temporal distance (use incident's last_updated)
    time_diff = calculate_temporal_distance(event.timestamp, incident.last_updated)

    # Disaster type
    type_match, type_score = calculate_disaster_type_score(
        getattr(event, 'event_type', None), incident_type
    )

    # For semantic similarity, we'd need the incident embedding
    # As a proxy, we can use a pre-computed incident embedding or skip
    # For now, use a neutral semantic score when incident embedding unavailable
    semantic_sim = 0.5  # Neutral placeholder

    return calculate_relationship_score(
        semantic_similarity=semantic_sim,
        geographic_distance_meters=distance,
        temporal_distance_minutes=time_diff,
        disaster_type_match=type_match,
        disaster_type_score=type_score,
    )


async def calculate_event_event_similarity(
    event1: Event,
    event2: Event,
    embedding1: Optional[List[float]],
    embedding2: Optional[List[float]],
    db: AsyncSession,
) -> RelationshipScore:
    """Calculate relationship score between two events."""
    # Semantic similarity
    if embedding1 and embedding2:
        semantic_sim = cosine_similarity(embedding1, embedding2)
    else:
        semantic_sim = 0.5  # Neutral if no embeddings

    # Geographic distance
    distance = await calculate_geographic_distance(
        event1.latitude, event1.longitude, event2.latitude, event2.longitude, db
    )

    # Temporal distance
    time_diff = calculate_temporal_distance(event1.timestamp, event2.timestamp)

    # Disaster type
    type_match, type_score = calculate_disaster_type_score(
        getattr(event1, 'event_type', None), getattr(event2, 'event_type', None)
    )

    return calculate_relationship_score(
        semantic_similarity=semantic_sim,
        geographic_distance_meters=distance,
        temporal_distance_minutes=time_diff,
        disaster_type_match=type_match,
        disaster_type_score=type_score,
    )