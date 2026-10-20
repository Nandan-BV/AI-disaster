from typing import List, Dict, Any, Optional
from uuid import UUID
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2 import Geography, WKTElement
from geoalchemy2.functions import ST_Distance, ST_SetSRID, ST_MakePoint

from app.config import settings
from app.models.resource import Resource, ResourceType, ResourceStatus
from app.models.incident import Incident
from app.models.risk import ResourceDemand


@dataclass
class SuitabilityResult:
    resource_id: UUID
    resource_name: str
    resource_type: str
    suitability_score: float  # 0-1
    matched_capabilities: List[str]
    missing_capabilities: List[str]
    distance_meters: float
    is_available: bool
    distance_score: float  # 0-1
    capability_score: float  # 0-1
    status_score: float  # 0-1
    reason: str


class SuitabilityService:
    """Service for evaluating resource suitability for demands."""

    # Resource type compatibility matrix
    TYPE_COMPATIBILITY = {
        "ambulance": ["ambulance", "emergency_vehicle"],
        "rescue_team": ["rescue_team", "emergency_vehicle"],
        "fire_vehicle": ["fire_vehicle"],
        "police_unit": ["police_unit", "emergency_vehicle"],
        "shelter": ["shelter"],
        "hospital": ["hospital", "emergency_vehicle"],
        "drone": ["drone"],
        "emergency_vehicle": ["emergency_vehicle", "ambulance", "rescue_team"],
    }

    # Minimum capability requirements by resource type
    MIN_CAPABILITIES = {
        "ambulance": ["medical"],
        "rescue_team": ["heavy_rescue", "rope_rescue"],
        "fire_vehicle": ["fire_suppression"],
        "police_unit": ["traffic_control", "crowd_management"],
        "shelter": ["capacity"],
        "hospital": ["emergency", "icu"],
        "drone": ["aerial_surveillance"],
        "emergency_vehicle": ["communications", "command_control"],
    }

    def __init__(self):
        pass

    def calculate_suitability(
        self,
        resource,
        demand,
        incident_location: tuple
    ) -> "SuitabilityResult":
        """
        Calculate suitability of a resource for a demand.
        
        Returns a SuitabilityResult with detailed scoring breakdown.
        """
        from app.models.resource import Resource, ResourceType, ResourceStatus
        
        # Convert resource to consistent format
        if hasattr(resource, 'resource_type'):
            resource_type = resource.resource_type.value
            status = resource.status.value
            capabilities = resource.capabilities or {}
            capacity = resource.capacity or 0
            current_load = resource.current_load or 0
            latitude = resource.latitude
            longitude = resource.longitude
            resource_id = resource.id
            name = resource.name
        else:
            # Dictionary format
            resource_type = resource.get('resource_type')
            status = resource.get('status')
            capabilities = resource.get('capabilities', {})
            capacity = resource.get('capacity', 0)
            current_load = resource.get('current_load', 0)
            latitude = resource.get('latitude')
            longitude = resource.get('longitude')
            resource_id = resource.get('id')
            name = resource.get('name', 'Unknown')

        # 1. Type compatibility check
        required_type = demand.get('resource_type', '')
        compatible_types = self.TYPE_COMPATIBILITY.get(demand.get('resource_type', ''), [])
        type_match = resource_type in compatible_types
        
        if not type_match:
            return self._create_result(
                resource_id=resource_id,
                name=name,
                resource_type=resource_type,
                suitability_score=0.0,
                reason=f"Resource type '{resource_type}' not compatible with required '{demand.get('resource_type')}'",
                is_available=False,
                distance_meters=0,
                distance_score=0,
                capability_score=0,
                status_score=0,
                missing_capabilities=[],
            )

        # 2. Status check
        status = status.value if hasattr(status, 'value') else status
        is_available = status == "available"
        status_score = 1.0 if is_available else 0.2  # Deployed/maintenance = 0.2, unavailable = 0
        
        # 3. Capability matching
        required_caps = demand.get('minimum_capability', {}) or {}
        matched_caps = []
        missing_caps = []
        
        for cap, required in (demand.get('minimum_capability', {}) or {}).items():
            if required and capabilities.get(cap):
                matched_caps.append(cap)
            elif required:
                missing_caps.append(cap)
        
        capability_score = len(matched_caps) / max(len(required_caps), 1) if required_caps else 0.5
        
        if missing_caps:
            capability_score *= 0.5  # Penalize missing capabilities
        
        # 4. Distance calculation
        distance = None
        distance_score = 0.5  # default
        if latitude and longitude and incident_location:
            from app.services.geospatial_service import haversine_distance
            distance = haversine_distance(
                latitude, longitude,
                incident_location[0], incident_location[1]
            )
            # Score: 1.0 at 0m, 0 at max distance
            max_dist = 50000  # 50km max
            distance_score = max(0, 1 - (distance / max_dist))
        
        # 5. Capacity utilization
        capacity_score = 1.0
        if capacity and demand.get('required_quantity', 0) > 0:
            # For capacity-constrained resources
            pass
        
        # Calculate overall suitability
        weights = {
            'distance': 0.3,
            'capability': 0.4,
            'status': 0.2,
            'capacity': 0.1,
        }
        
        suitability_score = (
            distance_score * weights['distance'] +
            capability_score * weights['capability'] +
            status_score * weights['status'] +
            capacity_score * weights['capacity']
        )
        
        # Build reason string
        reasons = []
        if not type_match:
            reasons.append(f"Type mismatch (need {demand.get('resource_type')}, got {resource_type})")
        if not is_available:
            reasons.append(f"Status: {status}")
        if missing_caps:
            reasons.append(f"Missing: {', '.join(missing_caps)}")
        if distance and distance > 50000:
            reasons.append(f"Distance: {distance/1000:.1f}km (exceeds limit)")
        
        reason = "; ".join(reasons) if reasons else "Suitable"
        
        return SuitabilityResult(
            resource_id=resource_id,
            resource_name=name,
            resource_type=resource_type,
            suitability_score=round(suitability_score, 3),
            matched_capabilities=matched_caps,
            missing_capabilities=missing_caps,
            distance_meters=distance or 0,
            is_available=is_available,
            distance_score=round(distance_score, 3),
            capability_score=round(capability_score, 3),
            status_score=round(status_score, 3),
            reason=reason,
        )
    
    def _create_result(
        self,
        resource_id,
        name,
        resource_type,
        suitability_score,
        reason,
        is_available,
        distance_meters,
        distance_score,
        capability_score,
        status_score,
        missing_capabilities,
    ) -> "SuitabilityResult":
        from app.services.suitability_service import SuitabilityResult
        return SuitabilityResult(
            resource_id=resource_id,
            resource_name=name,
            resource_type=resource_type,
            suitability_score=suitability_score,
            matched_capabilities=[],
            missing_capabilities=missing_capabilities,
            distance_meters=distance_meters,
            is_available=is_available,
            distance_score=distance_score,
            capability_score=capability_score,
            status_score=0.0,
            reason=reason,
        )


async def evaluate_resource_suitability(
    resource,
    demand: Dict[str, Any],
    incident_location: tuple,
    db
) -> "SuitabilityResult":
    """Evaluate a single resource's suitability for a demand."""
    service = SuitabilityService()
    
    # Get incident location
    incident_lat, incident_lon = incident_location
    
    # Build resource dict for evaluation
    if hasattr(resource, 'id'):
        resource_dict = {
            'id': resource.id,
            'name': resource.name,
            'resource_type': resource.resource_type.value,
            'status': resource.status.value,
            'capabilities': resource.capabilities or {},
            'capacity': resource.capacity,
            'current_load': resource.current_load,
            'latitude': resource.latitude,
            'longitude': resource.longitude,
        }
    else:
        resource_dict = resource
    
    # Get incident location for distance calculation
    incident_location = (incident_lat, incident_lon)
    
    return service.calculate_suitability(resource_dict, demand, incident_location)


async def find_suitable_resources(
    demands: List[Dict[str, Any]],
    incident_location: tuple,
    db,
    resource_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 100
) -> Dict[str, List[dict]]:
    """
    Find suitable resources for all demands.
    Returns a dict mapping resource_type -> list of suitable resources with scores.
    """
    from app.models.resource import Resource, ResourceType, ResourceStatus
    from sqlalchemy import select, func
    from geoalchemy2.functions import ST_Distance, ST_SetSRID, ST_MakePoint
    
    lat, lon = incident_location
    search_point = f"POINT({lon} {lat})"
    
    # Build base query
    query = select(Resource).where(
        Resource.status == ResourceStatus.AVAILABLE
    )
    
    if resource_type:
        query = query.where(Resource.resource_type == ResourceType(resource_type))
    
    # Add distance filter
    radius = 50000  # 50km max
    search_point = f"POINT({incident_location[1]} {incident_location[0]})"
    query = query.where(
        func.ST_Distance(
            Resource.location.cast(Geography(srid=4326)),
            func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326).cast(Geography(srid=4326))
        ) <= 50000
    )
    
    result = await db.execute(query)
    resources = result.scalars().all()
    
    # Evaluate each resource against all demands
    results = {}
    for demand in demands:
        suitable = []
        for resource in resources:
            # Check type compatibility
            # Evaluate suitability
            pass
    
    return results