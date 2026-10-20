from typing import Optional, List, Dict, Any
from uuid import UUID
from dataclasses import dataclass
from datetime import datetime
import json
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2 import Geography, WKTElement
from geoalchemy2.functions import ST_Distance, ST_SetSRID, ST_MakePoint, ST_AsGeoJSON

from app.config import settings
from app.models.resource import Resource, ResourceType, ResourceStatus
from app.models.incident import Incident


@dataclass
class NearbyResource:
    id: UUID
    name: str
    resource_type: str
    status: str
    distance_meters: float
    latitude: float
    longitude: float
    address: Optional[str]
    capacity: Optional[int]
    current_load: Optional[int]
    capabilities: Optional[Dict[str, Any]]
    organization: Optional[str]


@dataclass
class ResourceCountSummary:
    counts: Dict[str, int]


class ResourceService:
    def __init__(self, db):
        self.db = db

    async def get_resource_by_id(self, resource_id: UUID) -> Optional[Resource]:
        """Get a resource by ID."""
        result = await self.db.execute(
            select(Resource).where(Resource.id == resource_id)
        )
        return result.scalar_one_or_none()

    async def create_resource(self, resource_data: dict) -> Resource:
        """Create a new resource."""
        point = WKTElement(f"POINT({resource_data['longitude']} {resource_data['latitude']})", srid=4326)
        
        resource = Resource(
            name=resource_data['name'],
            resource_type=resource_data['resource_type'],
            status=resource_data['status'],
            latitude=resource_data['latitude'],
            longitude=resource_data['longitude'],
            location=WKTElement(f"POINT({resource_data['longitude']} {resource_data['latitude']})", srid=4326),
            address=resource_data.get('address'),
            capacity=resource_data.get('capacity'),
            current_load=resource_data.get('current_load', 0),
            capabilities=resource_data.get('capabilities', {}),
            organization=resource_data.get('organization'),
            metadata=resource_data.get('metadata', {}),
        )
        
        self.db.add(resource)
        await self.db.commit()
        await self.db.refresh(resource)
        return resource

    async def update_resource(self, resource_id: UUID, update_data: dict) -> Optional[Resource]:
        """Update a resource."""
        resource = await self.get_resource_by_id(resource_id)
        if not resource:
            return None
        
        for key, value in update_data.items():
            if value is not None:
                if key in ['latitude', 'longitude']:
                    # Update location point
                    if 'latitude' in update_data and 'longitude' in update_data:
                        resource.location = WKTElement(
                            f"POINT({update_data['longitude']} {update_data['latitude']})", srid=4326
                        )
                    elif key == 'latitude':
                        resource.latitude = value
                    elif key == 'longitude':
                        resource.longitude = value
                elif key == 'resource_type' or key == 'status':
                    setattr(resource, key, value)
                else:
                    setattr(resource, key, value)
        
        resource.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(resource)
        return resource

    async def update_resource_status(self, resource_id: UUID, status: str) -> Optional[Resource]:
        """Update just the status of a resource."""
        resource = await self.get_resource_by_id(resource_id)
        if not resource:
            return None
        
        resource.status = status
        resource.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(resource)
        return resource

    async def delete_resource(self, resource_id: UUID) -> bool:
        """Delete a resource."""
        resource = await self.get_resource_by_id(resource_id)
        if not resource:
            return False
        
        await self.db.delete(resource)
        await self.db.commit()
        return True

    async def list_resources(
        self,
        resource_type: Optional[str] = None,
        status: Optional[str] = None,
        organization: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Resource]:
        """List resources with optional filters."""
        query = select(Resource)
        
        if resource_type:
            query = query.where(Resource.resource_type == resource_type)
        if status:
            query = query.where(Resource.status == status)
        if organization:
            query = query.where(Resource.organization.ilike(f"%{organization}%"))
        
        query = query.order_by(Resource.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_nearby_resources(
        self,
        latitude: float,
        longitude: float,
        radius_meters: Optional[float] = None,
        resource_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[dict]:
        """Find resources near a point using PostGIS spatial queries."""
        radius = min(radius_meters or settings.DEFAULT_RESOURCE_SEARCH_RADIUS_METERS, 
                     settings.MAX_RESOURCE_SEARCH_RADIUS_METERS)
        
        # Build query with spatial distance calculation
        query = select(
            Resource.id,
            Resource.name,
            Resource.resource_type,
            Resource.status,
            Resource.latitude,
            Resource.longitude,
            Resource.address,
            Resource.capacity,
            Resource.current_load,
            Resource.capabilities,
            Resource.organization,
            Resource.metadata,
            func.ST_Distance(
                Resource.location.cast(Geography(srid=4326)),
                func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326).cast(Geography(srid=4326))
            ).label('distance_meters')
        ).where(
            func.ST_Distance(
                Resource.location.cast(Geography(srid=4326)),
                func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326).cast(Geography(srid=4326))
            ) <= radius
        )
        
        # Add filters
        if resource_type:
            query = query.where(Resource.resource_type == resource_type)
        if status:
            query = query.where(Resource.status == status)
        
        # Order by distance and limit
        query = query.order_by('distance_meters').limit(limit)
        
        result = await self.db.execute(query)
        rows = result.all()
        
        nearby = []
        for row in rows:
            nearby.append({
                'id': row.id,
                'name': row.name,
                'resource_type': row.resource_type.value,
                'status': row.status.value,
                'distance_meters': round(float(row.distance_meters), 2),
                'latitude': row.latitude,
                'longitude': row.longitude,
                'address': row.address,
                'capacity': row.capacity,
                'current_load': row.current_load,
                'capabilities': row.capabilities or {},
                'organization': row.organization,
            })
        
        return nearby

    async def get_resources_by_type(
        self,
        latitude: float,
        longitude: float,
        resource_type: str,
        radius_meters: Optional[float] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        """Get nearby resources of a specific type."""
        return await self.get_nearby_resources(
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters,
            resource_type=resource_type,
            status=status,
            limit=limit,
        )

    async def get_resource_counts_by_type(
        self,
        latitude: float,
        longitude: float,
        radius_meters: Optional[float] = None,
    ) -> Dict[str, int]:
        """Get counts of nearby resources grouped by type."""
        radius = radius_meters or settings.DEFAULT_RESOURCE_SEARCH_RADIUS_METERS
        radius = min(radius, settings.MAX_RESOURCE_SEARCH_RADIUS_METERS)
        
        search_point = WKTElement(f"POINT({longitude} {latitude})", srid=4326)
        
        query = select(
            Resource.resource_type,
            func.count(Resource.id).label('count')
        ).where(
            func.ST_Distance(
                Resource.location.cast(Geography(srid=4326)),
                func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326).cast(Geography(srid=4326))
            ) <= radius
        ).group_by(Resource.resource_type)
        
        result = await self.db.execute(query)
        return {row.resource_type.value: row.count for row in result.all()}

    async def get_resources_for_incident(
        self,
        incident_id: UUID,
        radius_meters: Optional[float] = None,
        resource_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[dict]:
        """Get nearby resources for a specific incident."""
        # Get incident location
        result = await self.db.execute(
            select(Incident.centroid_latitude, Incident.centroid_longitude)
            .where(Incident.id == incident_id)
        )
        row = result.first()
        if not row or row[0] is None or row[1] is None:
            raise ValueError(f"Incident {incident_id} has no valid coordinates")
        
        lat, lon = row[0], row[1]
        return await self.get_nearby_resources(
            latitude=lat,
            longitude=lon,
            radius_meters=radius_meters,
            resource_type=resource_type,
            status=status,
            limit=limit,
        )

    async def get_resource_counts_for_incident(
        self,
        incident_id: UUID,
        radius_meters: Optional[float] = None,
    ) -> Dict[str, int]:
        """Get counts of nearby resources by type for an incident."""
        result = await self.db.execute(
            select(Incident.centroid_latitude, Incident.centroid_longitude)
            .where(Incident.id == incident_id)
        )
        row = result.first()
        if not row or row[0] is None or row[1] is None:
            raise ValueError(f"Incident {incident_id} has no valid coordinates")
        
        lat, lon = row[0], row[1]
        return await self.get_resource_counts_by_type(lat, lon, radius_meters)

    async def get_resource_geojson(
        self,
        latitude: float,
        longitude: float,
        radius_meters: Optional[float] = None,
        resource_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> dict:
        """Get resources as GeoJSON FeatureCollection."""
        radius = min(radius_meters or settings.DEFAULT_RESOURCE_SEARCH_RADIUS_METERS,
                     settings.MAX_RESOURCE_SEARCH_RADIUS_METERS)
        
        search_point = WKTElement(f"POINT({longitude} {latitude})", srid=4326)
        
        query = select(
            Resource.id,
            Resource.name,
            Resource.resource_type,
            Resource.status,
            Resource.latitude,
            Resource.longitude,
            Resource.address,
            Resource.capacity,
            Resource.current_load,
            Resource.capabilities,
            Resource.organization,
            Resource.metadata,
            func.ST_AsGeoJSON(Resource.location).label('geojson')
        ).where(
            func.ST_Distance(
                Resource.location.cast(Geography(srid=4326)),
                func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326).cast(Geography(srid=4326))
            ) <= radius
        )
        
        if resource_type:
            query = query.where(Resource.resource_type == resource_type)
        if status:
            query = query.where(Resource.status == status)
        
        query = query.limit(200)
        result = await self.db.execute(query)
        rows = result.all()
        
        features = []
        for row in rows:
            geojson = row.geojson
            if isinstance(geojson, str):
                import json
                geojson = json.loads(geojson)
            
            features.append({
                "type": "Feature",
                "properties": {
                    "id": str(row.id),
                    "name": row.name,
                    "type": row.resource_type.value,
                    "status": row.status.value,
                    "distance_meters": round(float(row.distance_meters), 2) if hasattr(row, 'distance_meters') else 0,
                    "capacity": row.capacity,
                    "current_load": row.current_load,
                    "address": row.address,
                },
                "geometry": geojson
            })
        
        return {
            "type": "FeatureCollection",
            "features": features
        }