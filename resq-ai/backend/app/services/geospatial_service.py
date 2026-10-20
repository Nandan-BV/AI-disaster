import json
from typing import Optional, List, Dict, Any
from uuid import UUID
from dataclasses import dataclass
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2 import Geography, Geometry, WKTElement
from geoalchemy2.functions import ST_Distance, ST_Buffer, ST_AsGeoJSON, ST_Transform, ST_SetSRID, ST_MakePoint
from geoalchemy2.shape import to_shape

from app.config import settings
from app.models.infrastructure import (
    Infrastructure, InfrastructureType, InfrastructureStatus, RoadStatus, IncidentAnalysisArea
)
from app.models.incident import Incident


@dataclass
class NearbyInfrastructure:
    id: UUID
    name: str
    infrastructure_type: str
    distance_meters: float
    latitude: float
    longitude: float
    status: str
    capacity: Optional[int]
    address: Optional[str]
    road_status: Optional[str]
    metadata: Dict[str, Any]


@dataclass
class AffectedInfrastructureSummary:
    hospitals_nearby: List[NearbyInfrastructure]
    shelters_nearby: List[NearbyInfrastructure]
    fire_stations_nearby: List[NearbyInfrastructure]
    police_stations_nearby: List[NearbyInfrastructure]
    schools_nearby: List[NearbyInfrastructure]
    bridges_nearby: List[NearbyInfrastructure]
    roads_nearby: List[NearbyInfrastructure]
    emergency_centers_nearby: List[NearbyInfrastructure]
    power_stations_nearby: List[NearbyInfrastructure]
    water_facilities_nearby: List[NearbyInfrastructure]
    total_count: int


class GeospatialService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_incident_location(self, incident_id: UUID) -> Optional[tuple]:
        """Get incident coordinates (latitude, longitude)."""
        result = await self.db.execute(
            select(Incident.centroid_latitude, Incident.centroid_longitude)
            .where(Incident.id == incident_id)
        )
        row = result.first()
        if row and row[0] is not None and row[1] is not None:
            return (row[0], row[1])
        return None

    async def create_analysis_area(
        self,
        incident_id: UUID,
        radius_meters: Optional[float] = None
    ) -> IncidentAnalysisArea:
        """Create or update the analysis area (buffer) for an incident."""
        radius = radius_meters or settings.DEFAULT_INCIDENT_RADIUS_METERS
        incident_location = await self.get_incident_location(incident_id)

        if not incident_location:
            raise ValueError(f"Incident {incident_id} has no valid coordinates")

        lat, lon = incident_location
        # Create point and buffer using PostGIS
        point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
        # Use geography for accurate buffer in meters
        buffer_geom = ST_Buffer(point.cast(Geography(srid=4326)), radius).cast(Geometry(srid=4326))

        # Check if area already exists
        result = await self.db.execute(
            select(IncidentAnalysisArea).where(IncidentAnalysisArea.incident_id == incident_id)
        )
        area = result.scalar_one_or_none()

        if area:
            area.geometry = buffer_geom
            area.radius_meters = radius
        else:
            area = IncidentAnalysisArea(
                incident_id=incident_id,
                geometry=buffer_geom,
                radius_meters=radius,
            )
            self.db.add(area)

        await self.db.commit()
        await self.db.refresh(area)
        return area

    async def get_analysis_area(self, incident_id: UUID) -> Optional[IncidentAnalysisArea]:
        """Get the analysis area for an incident."""
        result = await self.db.execute(
            select(IncidentAnalysisArea).where(IncidentAnalysisArea.incident_id == incident_id)
        )
        return result.scalar_one_or_none()

    async def get_nearby_infrastructure(
        self,
        incident_id: UUID,
        radius_meters: Optional[float] = None,
        infrastructure_type: Optional[InfrastructureType] = None,
        status: Optional[InfrastructureStatus] = None,
        limit: int = 100,
    ) -> List[NearbyInfrastructure]:
        """Find infrastructure near an incident using PostGIS spatial queries."""
        incident_location = await self.get_incident_location(incident_id)
        if not incident_location:
            raise ValueError(f"Incident {incident_id} has no valid coordinates")

        lat, lon = incident_location
        radius = min(radius_meters or settings.DEFAULT_INCIDENT_RADIUS_METERS, settings.MAX_INFRASTRUCTURE_RADIUS_METERS)

        # Create incident point
        incident_point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)

        # Build query with spatial distance calculation
        query = select(
            Infrastructure.id,
            Infrastructure.name,
            Infrastructure.infrastructure_type,
            Infrastructure.latitude,
            Infrastructure.longitude,
            Infrastructure.status,
            Infrastructure.capacity,
            Infrastructure.address,
            Infrastructure.road_status,
            Infrastructure.metadata,
            ST_Distance(
                Infrastructure.location.cast(Geography(srid=4326)),
                incident_point.cast(Geography(srid=4326))
            ).label('distance_meters')
        ).where(
            ST_Distance(
                Infrastructure.location.cast(Geography(srid=4326)),
                incident_point.cast(Geography(srid=4326))
            ) <= radius
        )

        # Add filters
        if infrastructure_type:
            query = query.where(Infrastructure.infrastructure_type == infrastructure_type)
        if status:
            query = query.where(Infrastructure.status == status)

        # Order by distance and limit
        query = query.order_by('distance_meters').limit(limit)

        result = await self.db.execute(query)
        rows = result.all()

        nearby = []
        for row in rows:
            nearby.append(NearbyInfrastructure(
                id=row.id,
                name=row.name,
                infrastructure_type=row.infrastructure_type.value,
                distance_meters=round(float(row.distance_meters), 2),
                latitude=row.latitude,
                longitude=row.longitude,
                status=row.status.value,
                capacity=row.capacity,
                address=row.address,
                road_status=row.road_status.value if row.road_status else None,
                metadata=row.metadata or {},
            ))

        return nearby

    async def get_nearby_by_type(
        self,
        incident_id: UUID,
        infrastructure_type: InfrastructureType,
        radius_meters: Optional[float] = None,
        status: Optional[InfrastructureStatus] = None,
        limit: int = 50,
    ) -> List[NearbyInfrastructure]:
        """Get nearby infrastructure of a specific type."""
        return await self.get_nearby_infrastructure(
            incident_id=incident_id,
            radius_meters=radius_meters,
            infrastructure_type=infrastructure_type,
            status=status,
            limit=limit,
        )

    async def analyze_affected_infrastructure(
        self,
        incident_id: UUID,
        radius_meters: Optional[float] = None,
    ) -> AffectedInfrastructureSummary:
        """Analyze all infrastructure within the incident analysis radius."""
        radius = radius_meters or settings.DEFAULT_INCIDENT_RADIUS_METERS

        # Get all nearby infrastructure
        all_nearby = await self.get_nearby_infrastructure(
            incident_id=incident_id,
            radius_meters=radius,
            limit=500,
        )

        # Categorize by type
        categories = {
            'hospitals_nearby': [i for i in all_nearby if i.infrastructure_type == 'hospital'],
            'shelters_nearby': [i for i in all_nearby if i.infrastructure_type == 'shelter'],
            'fire_stations_nearby': [i for i in all_nearby if i.infrastructure_type == 'fire_station'],
            'police_stations_nearby': [i for i in all_nearby if i.infrastructure_type == 'police_station'],
            'schools_nearby': [i for i in all_nearby if i.infrastructure_type == 'school'],
            'bridges_nearby': [i for i in all_nearby if i.infrastructure_type == 'bridge'],
            'roads_nearby': [i for i in all_nearby if i.infrastructure_type == 'road'],
            'emergency_centers_nearby': [i for i in all_nearby if i.infrastructure_type == 'emergency_center'],
            'power_stations_nearby': [i for i in all_nearby if i.infrastructure_type == 'power_station'],
            'water_facilities_nearby': [i for i in all_nearby if i.infrastructure_type == 'water_facility'],
        }

        return AffectedInfrastructureSummary(
            hospitals_nearby=categories['hospitals_nearby'],
            shelters_nearby=categories['shelters_nearby'],
            fire_stations_nearby=categories['fire_stations_nearby'],
            police_stations_nearby=categories['police_stations_nearby'],
            schools_nearby=categories['schools_nearby'],
            bridges_nearby=categories['bridges_nearby'],
            roads_nearby=categories['roads_nearby'],
            emergency_centers_nearby=categories['emergency_centers_nearby'],
            power_stations_nearby=categories['power_stations_nearby'],
            water_facilities_nearby=categories['water_facilities_nearby'],
            total_count=len(all_nearby),
        )

    async def get_incident_map_data(self, incident_id: UUID) -> Dict[str, Any]:
        """Get GeoJSON data for map visualization."""
        incident_result = await self.db.execute(
            select(Incident).where(Incident.id == incident_id)
        )
        incident = incident_result.scalar_one_or_none()
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        # Get analysis area
        area = await self.get_analysis_area(incident_id)
        area_geojson = None
        if area:
            result = await self.db.execute(
                select(ST_AsGeoJSON(area.geometry))
            )
            area_geojson = result.scalar()
            if isinstance(area_geojson, str):
                area_geojson = json.loads(area_geojson)

        # Get nearby infrastructure
        nearby = await self.get_nearby_infrastructure(incident_id, limit=200)

        # Build GeoJSON FeatureCollection
        features = []

        # Incident point
        if incident.centroid_latitude is not None and incident.centroid_longitude is not None:
            features.append({
                "type": "Feature",
                "properties": {
                    "id": str(incident.id),
                    "name": incident.title,
                    "type": incident.incident_type,
                    "status": incident.status.value,
                    "event_count": incident.event_count,
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [incident.centroid_longitude, incident.centroid_latitude]
                }
            })

        # Analysis area polygon
        if area_geojson:
            features.append({
                "type": "Feature",
                "properties": {
                    "id": f"area-{incident.id}",
                    "name": "Analysis Area",
                    "radius_meters": area.radius_meters if area else 0,
                },
                "geometry": area_geojson
            })

        # Infrastructure points
        for infra in nearby:
            features.append({
                "type": "Feature",
                "properties": {
                    "id": str(infra.id),
                    "name": infra.name,
                    "type": infra.infrastructure_type,
                    "status": infra.status,
                    "distance_meters": infra.distance_meters,
                    "capacity": infra.capacity,
                    "address": infra.address,
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [infra.longitude, infra.latitude]
                }
            })

        return {
            "type": "FeatureCollection",
            "features": features
        }

    async def get_infrastructure_count_by_type(
        self,
        incident_id: UUID,
        radius_meters: Optional[float] = None,
    ) -> Dict[str, int]:
        """Get counts of nearby infrastructure grouped by type."""
        nearby = await self.get_nearby_infrastructure(incident_id, radius_meters=radius_meters, limit=500)
        counts = {}
        for infra in nearby:
            counts[infra.infrastructure_type] = counts.get(infra.infrastructure_type, 0) + 1
        return counts