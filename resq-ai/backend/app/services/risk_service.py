import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2 import Geography, WKTElement
from geoalchemy2.functions import ST_Distance, ST_Buffer, ST_Intersects, ST_Area, ST_SetSRID, ST_MakePoint
from geoalchemy2.shape import to_shape

from app.config import settings
from app.models.incident import Incident, IncidentEvent
from app.models.event import Event
from app.models.incident import IncidentEvent
from app.models.event_analysis import EventAIAnalysis
from app.models.incident import Incident
from app.models.evidence import IncidentInvestigation
from app.models.infrastructure import (
    Infrastructure,
    InfrastructureType,
    InfrastructureStatus,
    RoadStatus,
)
from app.models.risk import (
    PopulationZone, EnvironmentalConditions,
    RiskAssessment, ImpactAssessment, RiskAssessmentHistory,
    RiskLevel
)

logger = logging.getLogger(__name__)


def get_risk_level(score: float) -> RiskLevel:
    """Determine risk level from score."""
    if score <= settings.RISK_LEVEL_LOW_MAX:
        return RiskLevel.LOW
    elif score <= settings.RISK_LEVEL_MODERATE_MAX:
        return RiskLevel.MODERATE
    elif score <= settings.RISK_LEVEL_ELEVATED_MAX:
        return RiskLevel.ELEVATED
    elif score <= settings.RISK_LEVEL_HIGH_MAX:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


def calculate_severity_component(
    incident: Incident,
    ai_analysis: Optional[EventAIAnalysis],
    events: List[Event]
) -> tuple[float, Dict[str, Any]]:
    """
    Calculate severity component (0-100) based on AI analysis and event data.
    """
    details = {
        "ai_analysis_available": ai_analysis is not None,
        "event_count": len(events),
        "severity_indicators": [],
        "damage_reported": [],
        "people_affected": None,
    }
    
    if not ai_analysis:
        return 30.0, {**details, "note": "No AI analysis available"}
    
    score = 0.0
    
    # Base score from disaster type confidence
    if ai_analysis.disaster_type_confidence:
        score += ai_analysis.disaster_type_confidence * 40
    
    # Severity indicators
    if ai_analysis.severity_indicators:
        details["severity_indicators"] = ai_analysis.severity_indicators
        score += min(len(ai_analysis.severity_indicators) * 5, 30)
    
    # Damage observed
    if ai_analysis.damage_observed:
        details["damage_reported"] = ai_analysis.damage_observed
        score += min(len(ai_analysis.damage_observed) * 8, 25)
    
    # People affected (if explicitly reported)
    if ai_analysis.people_affected:
        details["people_affected"] = ai_analysis.people_affected
        score += 15
    
    # Infrastructure damage
    if ai_analysis.infrastructure_damage:
        details["infrastructure_damage"] = ai_analysis.infrastructure_damage
        score += min(len(ai_analysis.infrastructure_damage) * 5, 15)
    
    return min(score, 100.0), details


def calculate_evidence_component(
    incident_id: UUID,
    investigation: Optional[IncidentInvestigation],
    incident_events: List[IncidentEvent]
) -> tuple[float, Dict[str, Any]]:
    """
    Calculate evidence component (0-100) based on Phase 4 investigation.
    """
    details = {
        "investigation_available": investigation is not None,
        "event_count": len(incident_events),
        "evidence_confidence": 0.0,
        "supporting_evidence": 0,
        "contradicting_evidence": 0,
        "source_diversity": 0.0,
        "multimodal_consistency": 0.0,
    }
    
    if not investigation:
        return 20.0, {**details, "note": "No investigation available"}
    
    score = 0.0
    
    # Evidence confidence (0-40 points)
    if investigation.evidence_confidence:
        details["evidence_confidence"] = investigation.evidence_confidence
        score += investigation.evidence_confidence * 40
    
    # Supporting evidence (0-20 points)
    if investigation.supporting_evidence_count:
        details["supporting_evidence"] = investigation.supporting_evidence_count
        score += min(investigation.supporting_evidence_count * 4, 20)
    
    # Contradicting evidence reduces score (0 to -20 points)
    if investigation.contradicting_evidence_count:
        details["contradicting_evidence"] = investigation.contradicting_evidence_count
        score -= min(investigation.contradicting_evidence_count * 5, 20)
    
    # Source diversity (0-15 points)
    if investigation.source_diversity:
        details["source_diversity"] = investigation.source_diversity
        score += investigation.source_diversity * 15
    
    # Multimodal consistency (0-15 points)
    if investigation.multimodal_consistency:
        details["multimodal_consistency"] = investigation.multimodal_consistency
        score += investigation.multimodal_consistency * 15
    
    # Geographic consistency (0-10 points)
    if investigation.geographic_consistency:
        details["geographic_consistency"] = investigation.geographic_consistency
        score += investigation.geographic_consistency * 10
    
    return max(0.0, min(score, 100.0)), details


async def calculate_population_component(
    incident_id: UUID,
    db: AsyncSession,
    incident: Incident
) -> tuple[float, Dict[str, Any]]:
    """
    Calculate population exposure component (0-100).
    """
    details = {
        "population_potentially_exposed": 0,
        "population_zones_count": 0,
        "population_weighted_exposure": 0.0,
        "zones_affected": [],
    }
    
    if not incident.centroid_latitude or not incident.centroid_longitude:
        return 0.0, {**details, "note": "Incident has no coordinates"}
    
    radius = settings.DEFAULT_INCIDENT_RADIUS_METERS
    incident_point = ST_SetSRID(ST_MakePoint(incident.centroid_longitude, incident.centroid_latitude), 4326)
    
    # Find population zones within incident radius
    query = select(
        PopulationZone.id,
        PopulationZone.name,
        PopulationZone.population,
        PopulationZone.vulnerability_factor,
        PopulationZone.latitude,
        PopulationZone.longitude,
        ST_Distance(
            PopulationZone.location.cast(Geography(srid=4326)),
            incident_point.cast(Geography(srid=4326))
        ).label('distance_meters')
    ).where(
        ST_Distance(
            PopulationZone.location.cast(Geography(srid=4326)),
            incident_point.cast(Geography(srid=4326))
        ) <= settings.DEFAULT_INCIDENT_RADIUS_METERS
    )
    
    result = await db.execute(query)
    zones = result.all()
    
    if not zones:
        return 0.0, {**details, "note": "No population zones within analysis radius"}
    
    total_population = 0
    weighted_exposure = 0.0
    
    for zone in zones:
        distance = zone.distance_meters or 0
        # Weight by distance (closer = higher exposure)
        distance_weight = max(0, 1.0 - (distance / settings.DEFAULT_INCIDENT_RADIUS_METERS))
        vulnerability = zone.vulnerability_factor or 0.5
        
        exposure = zone.population * distance_weight * vulnerability
        weighted_exposure += exposure
        total_population += zone.population
        
        details["zones_affected"].append({
            "name": zone.name,
            "population": zone.population,
            "distance_meters": round(distance, 1),
            "vulnerability_factor": vulnerability,
            "exposure_score": round(exposure, 1),
        })
    
    details["population_potentially_exposed"] = total_population
    details["population_zones_count"] = len(zones)
    details["population_weighted_exposure"] = round(weighted_exposure, 1)
    
    # Score based on weighted exposure
    # 10,000 people = 50 points, scales up
    score = min(weighted_exposure / 200.0, 100.0)
    
    return score, details


async def calculate_infrastructure_component(
    incident_id: UUID,
    db: AsyncSession,
    incident: Incident
) -> tuple[float, Dict[str, Any]]:
    """
    Calculate infrastructure exposure component (0-100).
    """
    details = {
        "infrastructure_count": 0,
        "critical_infrastructure_score": 0.0,
        "by_type": {},
        "critical_infrastructure": [],
    }
    
    if not incident.centroid_latitude or not incident.centroid_longitude:
        return 0.0, {**details, "note": "Incident has no coordinates"}
    
    incident_point = ST_SetSRID(ST_MakePoint(incident.centroid_longitude, incident.centroid_latitude), 4326)
    
    query = select(
        Infrastructure.id,
        Infrastructure.name,
        Infrastructure.infrastructure_type,
        Infrastructure.status,
        Infrastructure.capacity,
        ST_Distance(
            Infrastructure.location.cast(Geography(srid=4326)),
            incident_point.cast(Geography(srid=4326))
        ).label('distance_meters')
    ).where(
        ST_Distance(
            Infrastructure.location.cast(Geography(srid=4326)),
            incident_point.cast(Geography(srid=4326))
        ) <= settings.DEFAULT_INCIDENT_RADIUS_METERS
    )
    
    result = await db.execute(query)
    infra_items = result.all()
    
    if not infra_items:
        return 0.0, {**details, "note": "No infrastructure within analysis radius"}
    
    total_weight = 0.0
    critical_count = 0
    
    infra_weights = {
        InfrastructureType.HOSPITAL: settings.INFRA_WEIGHT_HOSPITAL,
        InfrastructureType.SHELTER: settings.INFRA_WEIGHT_SHELTER,
        InfrastructureType.FIRE_STATION: settings.INFRA_WEIGHT_FIRE_STATION,
        InfrastructureType.POLICE_STATION: settings.INFRA_WEIGHT_POLICE_STATION,
        InfrastructureType.BRIDGE: settings.INFRA_WEIGHT_BRIDGE,
        InfrastructureType.ROAD: settings.INFRA_WEIGHT_ROAD,
        InfrastructureType.EMERGENCY_CENTER: settings.INFRA_WEIGHT_EMERGENCY_CENTER,
        InfrastructureType.POWER_STATION: settings.INFRA_WEIGHT_POWER_STATION,
        InfrastructureType.WATER_FACILITY: settings.INFRA_WEIGHT_WATER_FACILITY,
        InfrastructureType.SCHOOL: settings.INFRA_WEIGHT_SCHOOL,
    }
    
    for infra in infra_items:
        weight = infra_weights.get(infra.infrastructure_type, 1.0)
        distance = infra.distance_meters or 0
        distance_weight = max(0, 1.0 - (distance / settings.DEFAULT_INCIDENT_RADIUS_METERS))
        
        effective_weight = weight * distance_weight
        total_weight += effective_weight
        
        if infra.infrastructure_type in [InfrastructureType.HOSPITAL, InfrastructureType.SHELTER, 
                                          InfrastructureType.EMERGENCY_CENTER, InfrastructureType.FIRE_STATION]:
            critical_count += 1
            details["critical_infrastructure"].append({
                "name": infra.name,
                "type": infra.infrastructure_type.value,
                "distance_meters": round(distance, 1),
            })
        
        type_key = infra.infrastructure_type.value
        details["by_type"][type_key] = details["by_type"].get(type_key, 0) + 1
    
    details["infrastructure_count"] = len(infra_items)
    details["critical_infrastructure_score"] = round(total_weight, 1)
    
    # Score based on weighted infrastructure
    score = min(total_weight * 2.0, 100.0)
    
    return score, details


async def calculate_environment_component(
    incident_id: UUID,
    db: AsyncSession,
    incident: Incident
) -> tuple[float, Dict[str, Any]]:
    """
    Calculate environmental conditions component (0-100).
    """
    details = {
        "conditions_available": False,
        "rainfall_mm": None,
        "wind_speed_kmh": None,
        "water_level_m": None,
        "temperature_c": None,
        "conditions_summary": "No environmental data",
    }
    
    # Get latest environmental conditions for this incident
    result = await db.execute(
        select(EnvironmentalConditions)
        .where(EnvironmentalConditions.incident_id == incident_id)
        .order_by(EnvironmentalConditions.timestamp.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    
    if not latest:
        return 10.0, {**details, "note": "No environmental data available"}
    
    details["conditions_available"] = True
    details["rainfall_mm"] = latest.rainfall
    details["wind_speed_kmh"] = latest.wind_speed
    details["water_level_m"] = latest.water_level
    details["temperature_c"] = latest.temperature
    
    score = 0.0
    
    # Rainfall (0-30 points)
    if latest.rainfall is not None:
        if latest.rainfall > 50:
            score += 30
        elif latest.rainfall > 20:
            score += 20
        elif latest.rainfall > 10:
            score += 10
        elif latest.rainfall > 5:
            score += 5
    
    # Wind speed (0-20 points)
    if latest.wind_speed is not None:
        if latest.wind_speed > 80:
            score += 20
        elif latest.wind_speed > 50:
            score += 15
        elif latest.wind_speed > 30:
            score += 10
        elif latest.wind_speed > 15:
            score += 5
    
    # Water level (0-30 points)
    if latest.water_level is not None:
        if latest.water_level > 2.0:
            score += 30
        elif latest.water_level > 1.0:
            score += 20
        elif latest.water_level > 0.5:
            score += 10
    
    # Temperature (0-10 points for extreme)
    if latest.temperature is not None:
        if latest.temperature > 40 or latest.temperature < 0:
            score += 10
    
    details["conditions_summary"] = f"Rain: {latest.rainfall}mm/h, Wind: {latest.wind_speed}km/h, Water: {latest.water_level}m"
    
    return min(score, 100.0), details


async def calculate_accessibility_component(
    incident_id: UUID,
    db: AsyncSession,
    incident: Incident
) -> tuple[float, Dict[str, Any]]:
    """
    Calculate accessibility component (0-100, lower is worse accessibility = higher risk).
    """
    details = {
        "roads_count": 0,
        "blocked_roads": 0,
        "partially_blocked_roads": 0,
        "open_roads": 0,
        "bridges_count": 0,
        "blocked_bridges": 0,
        "accessibility_score": 0.0,
    }
    
    if not incident.centroid_latitude or not incident.centroid_longitude:
        return 50.0, {**details, "note": "Incident has no coordinates"}
    
    incident_point = ST_SetSRID(ST_MakePoint(incident.centroid_longitude, incident.centroid_latitude), 4326)
    
    # Check roads
    roads_query = select(
        Infrastructure.id,
        Infrastructure.name,
        Infrastructure.road_status,
        ST_Distance(
            Infrastructure.location.cast(Geography(srid=4326)),
            incident_point.cast(Geography(srid=4326))
        ).label('distance_meters')
    ).where(
        and_(
            Infrastructure.infrastructure_type == InfrastructureType.ROAD,
            ST_Distance(
                Infrastructure.location.cast(Geography(srid=4326)),
                incident_point.cast(Geography(srid=4326))
            ) <= settings.DEFAULT_INCIDENT_RADIUS_METERS
        )
    )
    roads_result = await db.execute(roads_query)
    roads = roads_result.all()
    
    details["roads_count"] = len(roads)
    blocked_roads = sum(1 for r in roads if r.road_status == RoadStatus.BLOCKED)
    partially_blocked = sum(1 for r in roads if r.road_status == RoadStatus.PARTIALLY_BLOCKED)
    open_roads = sum(1 for r in roads if r.road_status == RoadStatus.OPEN)
    
    details["blocked_roads"] = blocked_roads
    details["partially_blocked_roads"] = partially_blocked
    details["open_roads"] = open_roads
    
    # Check bridges
    bridges_query = select(
        Infrastructure.id,
        Infrastructure.name,
        Infrastructure.road_status,
        ST_Distance(
            Infrastructure.location.cast(Geography(srid=4326)),
            incident_point.cast(Geography(srid=4326))
        ).label('distance_meters')
    ).where(
        and_(
            Infrastructure.infrastructure_type == InfrastructureType.BRIDGE,
            ST_Distance(
                Infrastructure.location.cast(Geography(srid=4326)),
                incident_point.cast(Geography(srid=4326))
            ) <= settings.DEFAULT_INCIDENT_RADIUS_METERS
        )
    )
    bridges_result = await db.execute(bridges_query)
    bridges = bridges_result.all()
    
    details["bridges_count"] = len(bridges)
    blocked_bridges = sum(1 for b in bridges if b.road_status == RoadStatus.BLOCKED)
    details["blocked_bridges"] = blocked_bridges
    
    # Calculate accessibility score (0-100, higher = better accessibility = lower risk)
    if not roads and not bridges:
        return 50.0, {**details, "note": "No road/bridge data available"}
    
    total_transport = len(roads) + len(bridges)
    if total_transport == 0:
        return 50.0, {**details, "note": "No transport infrastructure data"}
    
    blocked_total = blocked_roads + blocked_bridges
    partially_blocked_total = sum(1 for r in roads if r.road_status == RoadStatus.PARTIALLY_BLOCKED)
    
    accessibility_ratio = (details["open_roads"] + (total_transport - details["blocked_roads"] - len(bridges))) / max(total_transport, 1)
    
    # Score is inverse: better accessibility = lower risk component
    # 100 = fully accessible (low risk), 0 = completely blocked (high risk)
    accessibility_score = accessibility_ratio * 100
    details["accessibility_score"] = round(accessibility_score, 1)
    
    return min(max(accessibility_score, 0), 100.0), details


async def calculate_risk_assessment(
    incident_id: UUID,
    db: AsyncSession,
    trigger: str = "manual"
) -> RiskAssessment:
    """
    Calculate complete risk assessment for an incident.
    """
    # Load incident
    incident_result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = incident_result.scalar_one_or_none()
    if not incident:
        raise ValueError(f"Incident {incident_id} not found")
    
    # Load events for this incident
    events_result = await db.execute(
        select(Event)
        .join(IncidentEvent, Event.id == IncidentEvent.event_id)
        .where(IncidentEvent.incident_id == incident_id)
    )
    events = list(events_result.scalars().all())
    
    # Get latest AI analysis for any of the incident's events
    event_ids = [e.id for e in events]
    ai_analysis = None
    if event_ids:
        ai_result = await db.execute(
            select(EventAIAnalysis)
            .where(EventAIAnalysis.event_id.in_(event_ids))
            .order_by(EventAIAnalysis.created_at.desc())
            .limit(1)
        )
        ai_analysis = ai_result.scalar_one_or_none()
    
    # Get latest investigation
    inv_result = await db.execute(
        select(IncidentInvestigation)
        .where(IncidentInvestigation.incident_id == incident_id)
        .order_by(IncidentInvestigation.investigated_at.desc())
        .limit(1)
    )
    investigation = inv_result.scalar_one_or_none()
    
    # Get incident events for evidence
    incident_events = await db.execute(
        select(IncidentEvent).where(IncidentEvent.incident_id == incident_id)
    )
    incident_events = list(incident_events.scalars().all())
    
    # Calculate all components
    severity_score, severity_details = calculate_severity_component(incident, ai_analysis, events)
    evidence_score, evidence_details = calculate_evidence_component(incident_id, investigation, incident_events)
    population_score, population_details = await calculate_population_component(incident_id, db, incident)
    infrastructure_score, infrastructure_details = await calculate_infrastructure_component(incident_id, db, incident)
    environment_score, environment_details = await calculate_environment_component(incident_id, db, incident)
    accessibility_score, accessibility_details = await calculate_accessibility_component(incident_id, db, incident)
    
    # Weighted combination
    weights = {
        "severity": settings.RISK_WEIGHT_SEVERITY,
        "evidence": settings.RISK_WEIGHT_EVIDENCE,
        "population": settings.RISK_WEIGHT_POPULATION,
        "infrastructure": settings.RISK_WEIGHT_INFRASTRUCTURE,
        "environment": settings.RISK_WEIGHT_ENVIRONMENT,
        "accessibility": settings.RISK_WEIGHT_ACCESSIBILITY,
    }
    
    # Note: accessibility is inverse (higher accessibility = lower risk)
    # So we invert it for risk calculation
    accessibility_risk = 100 - accessibility_score
    
    total_score = (
        severity_score * weights["severity"] +
        evidence_score * weights["evidence"] +
        population_score * weights["population"] +
        infrastructure_score * weights["infrastructure"] +
        environment_score * weights["environment"] +
        accessibility_risk * weights["accessibility"]
    )
    
    risk_score = round(min(max(total_score, 0), 100), 1)
    risk_level = get_risk_level(risk_score)
    
    # Build explanation
    explanation_parts = []
    if severity_score > 60:
        explanation_parts.append(f"High severity (score: {severity_score:.1f})")
    elif severity_score > 30:
        explanation_parts.append(f"Moderate severity (score: {severity_score:.1f})")
    else:
        explanation_parts.append(f"Low severity (score: {severity_score:.1f})")
    
    if evidence_score > 60:
        explanation_parts.append(f"Strong evidence support (score: {evidence_score:.1f})")
    elif evidence_score < 30:
        explanation_parts.append(f"Limited evidence (score: {evidence_score:.1f})")
    
    if population_score > 60:
        explanation_parts.append(f"High population exposure (score: {population_score:.1f})")
    elif population_score > 30:
        explanation_parts.append(f"Moderate population exposure (score: {population_score:.1f})")
    
    if infrastructure_score > 60:
        explanation_parts.append(f"Significant infrastructure exposure (score: {infrastructure_score:.1f})")
    
    if environment_score > 60:
        explanation_parts.append(f"Adverse environmental conditions (score: {environment_score:.1f})")
    
    if accessibility_score < 40:
        explanation_parts.append(f"Poor accessibility (score: {accessibility_score:.1f})")
    
    explanation = ". ".join(explanation_parts) + "."
    
    # Create risk assessment
    assessment = RiskAssessment(
        incident_id=incident_id,
        risk_score=risk_score,
        risk_level=get_risk_level(risk_score),
        severity_component=round(severity_score, 1),
        evidence_component=round(evidence_score, 1),
        population_component=round(population_score, 1),
        infrastructure_component=round(infrastructure_score, 1),
        environment_component=round(environment_score, 1),
        accessibility_component=round(accessibility_score, 1),
        severity_details=severity_details,
        evidence_details=evidence_details,
        population_details=population_details,
        infrastructure_details=infrastructure_details,
        environment_details=environment_details,
        accessibility_details=accessibility_details,
        explanation=explanation,
        model_name=settings.AI_MODEL_NAME,
    )
    
    db.add(assessment)
    
    # Also add to history
    history = RiskAssessmentHistory(
        incident_id=incident_id,
        risk_score=risk_score,
        risk_level=get_risk_level(risk_score),
        severity_component=round(severity_score, 1),
        evidence_component=round(evidence_score, 1),
        population_component=round(population_score, 1),
        infrastructure_component=round(infrastructure_score, 1),
        environment_component=round(environment_score, 1),
        accessibility_component=round(accessibility_score, 1),
        explanation=explanation,
        trigger="manual",
    )
    db.add(history)
    
    await db.commit()
    await db.refresh(assessment)
    
    return assessment


async def calculate_impact_assessment(
    incident_id: UUID,
    db: AsyncSession
) -> ImpactAssessment:
    """
    Calculate impact assessment for an incident.
    """
    incident_result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = incident_result.scalar_one_or_none()
    if not incident:
        raise ValueError(f"Incident {incident_id} not found")
    
    if not incident.centroid_latitude or not incident.centroid_longitude:
        raise ValueError("Incident has no coordinates")
    
    incident_point = ST_SetSRID(ST_MakePoint(incident.centroid_longitude, incident.centroid_latitude), 4326)
    
    # Population exposure
    pop_query = select(
        func.sum(PopulationZone.population).label('total_pop'),
        func.count(PopulationZone.id).label('zone_count'),
        func.sum(PopulationZone.population * PopulationZone.vulnerability_factor).label('weighted_pop')
    ).where(
        ST_Distance(
            PopulationZone.location.cast(Geography(srid=4326)),
            incident_point.cast(Geography(srid=4326))
        ) <= settings.DEFAULT_INCIDENT_RADIUS_METERS
    )
    pop_result = await db.execute(pop_query)
    pop_row = pop_result.first()
    
    population_exposed = int(pop_row.total_pop) if pop_row.total_pop else 0
    zone_count = int(pop_row.zone_count) if pop_row.zone_count else 0
    weighted_exposure = float(pop_row.weighted_pop) if pop_row.weighted_pop else 0.0
    
    # Infrastructure counts by type
    infra_query = select(
        Infrastructure.infrastructure_type,
        func.count(Infrastructure.id).label('count')
    ).where(
        ST_Distance(
            Infrastructure.location.cast(Geography(srid=4326)),
            ST_SetSRID(ST_MakePoint(incident.centroid_longitude, incident.centroid_latitude), 4326).cast(Geography(srid=4326))
        ) <= settings.DEFAULT_INCIDENT_RADIUS_METERS
    ).group_by(Infrastructure.infrastructure_type)
    
    infra_result = await db.execute(infra_query)
    infra_counts = {row.infrastructure_type.value: row.count for row in infra_result.all()}
    
    # Road/bridge status
    incident_point = ST_SetSRID(ST_MakePoint(incident.centroid_longitude, incident.centroid_latitude), 4326)
    
    roads_query = select(Infrastructure.road_status).where(
        and_(
            Infrastructure.infrastructure_type == InfrastructureType.ROAD,
            ST_Distance(
                Infrastructure.location.cast(Geography(srid=4326)),
                ST_SetSRID(ST_MakePoint(incident.centroid_longitude, incident.centroid_latitude), 4326).cast(Geography(srid=4326))
            ) <= settings.DEFAULT_INCIDENT_RADIUS_METERS
        )
    )
    roads_result = await db.execute(roads_query)
    road_statuses = [r.road_status for r in roads_result.scalars().all()]
    
    blocked_roads = sum(1 for r in road_statuses if r == RoadStatus.BLOCKED)
    partially_blocked = sum(1 for r in road_statuses if r == RoadStatus.PARTIALLY_BLOCKED)
    open_roads = sum(1 for r in road_statuses if r == RoadStatus.OPEN)
    
    if blocked_roads > open_roads:
        accessibility_status = "blocked"
    elif partially_blocked > 0:
        accessibility_status = "partially_blocked"
    elif open_roads > 0:
        accessibility_status = "open"
    else:
        accessibility_status = "unknown"
    
    total_infra = sum(infra_counts.values())
    
    impact = ImpactAssessment(
        incident_id=incident_id,
        population_potentially_exposed=population_exposed,
        population_zones_count=zone_count,
        population_weighted_exposure=round(population_exposed, 1),
        infrastructure_potentially_exposed=total_infra,
        hospitals_count=infra_counts.get("hospital", 0),
        shelters_count=infra_counts.get("shelter", 0),
        fire_stations_count=infra_counts.get("fire_station", 0),
        police_stations_count=infra_counts.get("police_station", 0),
        schools_count=infra_counts.get("school", 0),
        bridges_count=infra_counts.get("bridge", 0),
        roads_count=infra_counts.get("road", 0),
        emergency_centers_count=infra_counts.get("emergency_center", 0),
        power_stations_count=infra_counts.get("power_station", 0),
        water_facilities_count=infra_counts.get("water_facility", 0),
        roads_potentially_affected=blocked_roads + (sum(1 for r in road_statuses if r == RoadStatus.PARTIALLY_BLOCKED)),
        bridges_potentially_affected=infra_counts.get("bridge", 0),
        accessibility_status=accessibility_status,
        accessibility_details={
            "open_roads": open_roads,
            "blocked_roads": sum(1 for r in road_statuses if r == RoadStatus.BLOCKED),
            "partially_blocked_roads": partially_blocked,
        },
        explanation=f"Incident analysis area contains {population_exposed} people across {zone_count} population zones. "
                    f"{total_infra} infrastructure elements within {settings.DEFAULT_INCIDENT_RADIUS_METERS}m radius. "
                    f"Road access: {accessibility_status}."
    )
    
    return impact


async def recalculate_risk(incident_id: UUID, db: AsyncSession) -> RiskAssessment:
    """Recalculate risk using latest data."""
    return await calculate_risk_assessment(incident_id, db, trigger="recalculate")


async def get_latest_risk_assessment(incident_id: UUID, db: AsyncSession) -> Optional[RiskAssessment]:
    result = await db.execute(
        select(RiskAssessment)
        .where(RiskAssessment.incident_id == incident_id)
        .order_by(RiskAssessment.assessed_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest_impact_assessment(incident_id: UUID, db: AsyncSession) -> Optional[ImpactAssessment]:
    result = await db.execute(
        select(ImpactAssessment)
        .where(ImpactAssessment.incident_id == incident_id)
        .order_by(ImpactAssessment.assessed_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_risk_history(incident_id: UUID, db: AsyncSession, limit: int = 20) -> List[RiskAssessmentHistory]:
    result = await db.execute(
        select(RiskAssessmentHistory)
        .where(RiskAssessmentHistory.incident_id == incident_id)
        .order_by(RiskAssessmentHistory.assessed_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())