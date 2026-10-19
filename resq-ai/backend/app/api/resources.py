from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.core.security import require_role
from app.models.resource import Resource, ResourceType, ResourceStatus
from app.models.incident import Incident
from app.schemas.resource import (
    ResourceCreate,
    ResourceUpdate,
    ResourceStatusUpdate,
    ResourceResponse,
    ResourceListResponse,
    NearbyResourceListResponse,
    ResourceCountResponse,
)
from app.services.resource_service import ResourceService

router = APIRouter(prefix="/resources", tags=["resources"])


# Resource CRUD endpoints
@router.post("", response_model=ResourceResponse, status_code=http_status.HTTP_201_CREATED)
async def create_resource(
    resource: ResourceCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new resource."""
    service = ResourceService(db)
    
    # Validate capacity/current_load constraints
    if resource.capacity is not None and resource.current_load is not None:
        if resource.current_load > resource.capacity:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="current_load cannot exceed capacity"
            )
    
    resource_data = resource.model_dump()
    db_resource = await service.create_resource(resource_data)
    return db_resource


@router.get("", response_model=ResourceListResponse)
async def list_resources(
    resource_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    organization: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List resources with optional filters."""
    service = ResourceService(db)
    
    resources = await service.list_resources(
        resource_type=resource_type,
        status=status,
        organization=organization,
        limit=limit,
        offset=offset,
    )
    
    # Get total count
    query = select(func.count(Resource.id))
    if resource_type:
        query = query.where(Resource.resource_type == resource_type)
    if status:
        query = query.where(Resource.status == status)
    if organization:
        query = query.where(Resource.organization.ilike(f"%{organization}%"))
    
    total_result = await db.execute(query)
    total = total_result.scalar()
    
    return ResourceListResponse(
        resources=[ResourceResponse.model_validate(r) for r in resources],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/nearby", response_model=NearbyResourceListResponse)
async def get_nearby_resources(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_meters: Optional[float] = Query(None, ge=100, le=10000),
    resource_type: Optional[str] = Query(None),
    resource_status: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Find resources near a point using PostGIS spatial queries."""
    if resource_type:
        try:
            ResourceType(resource_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid resource type: {resource_type}"
            )

    if resource_status:
        try:
            ResourceStatus(resource_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status: {resource_status}"
            )

    service = ResourceService(db)
    nearby = await service.get_nearby_resources(
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
        resource_type=resource_type,
        status=resource_status,
        limit=limit,
    )
    paginated = nearby[offset:offset + limit]
    return NearbyResourceListResponse(
        resources=paginated,
        total=len(nearby),
        limit=limit,
        offset=offset,
    )


@router.get("/nearby/counts", response_model=ResourceCountResponse)
async def get_nearby_resource_counts(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_meters: Optional[float] = Query(None, ge=100, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """Get counts of nearby resources grouped by type."""
    service = ResourceService(db)
    counts = await service.get_resource_counts_by_type(
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
    )
    return ResourceCountResponse(counts=counts)


@router.get("/{resource_id}", response_model=ResourceResponse)
async def get_resource(
    resource_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific resource by ID."""
    service = ResourceService(db)
    resource = await service.get_resource_by_id(resource_id)
    if not resource:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Resource {resource_id} not found"
        )
    return ResourceResponse.model_validate(resource)


@router.patch("/{resource_id}", response_model=ResourceResponse)
async def update_resource(
    resource_id: UUID,
    resource_update: ResourceUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a resource."""
    service = ResourceService(db)
    
    # Validate capacity/current_load constraints
    update_data = resource_update.model_dump(exclude_unset=True)
    if 'capacity' in update_data and 'current_load' in update_data:
        if update_data['current_load'] > update_data['capacity']:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="current_load cannot exceed capacity"
            )
    
    resource = await service.update_resource(resource_id, update_data)
    if not resource:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Resource {resource_id} not found"
        )
    return ResourceResponse.model_validate(resource)


@router.patch("/{resource_id}/status", response_model=ResourceResponse)
async def update_resource_status(
    resource_id: UUID,
    status_update: ResourceStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(require_role(["dispatcher", "commander", "admin"])),
):
    """Update just the status of a resource."""
    service = ResourceService(db)
    resource = await service.update_resource_status(resource_id, status_update.status)
    if not resource:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Resource {resource_id} not found"
        )
    return ResourceResponse.model_validate(resource)


@router.delete("/{resource_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_resource(
    resource_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a resource."""
    service = ResourceService(db)
    deleted = await service.delete_resource(resource_id)
    if not deleted:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Resource {resource_id} not found"
        )


<<<<<<< HEAD
# Nearby resource search endpoints
@router.get("/nearby", response_model=NearbyResourceListResponse)
async def get_nearby_resources(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_meters: Optional[float] = Query(None, ge=100, le=10000),
    resource_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Find resources near a point using PostGIS spatial queries."""
    # Validate resource_type if provided
    if resource_type:
        try:
            ResourceType(resource_type)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid resource type: {resource_type}"
            )
    
    # Validate status if provided
    if status:
        try:
            ResourceStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status: {status}"
            )
    
    service = ResourceService(db)
    nearby = await service.get_nearby_resources(
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
        resource_type=resource_type,
        status=status,
        limit=limit,
    )
    
    # Apply offset manually since we're doing it in Python
    paginated = nearby[offset:offset + limit]
    
    return NearbyResourceListResponse(
        resources=paginated,
        total=len(nearby),
        limit=limit,
        offset=offset,
    )


@router.get("/nearby/counts", response_model=ResourceCountResponse)
async def get_nearby_resource_counts(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_meters: Optional[float] = Query(None, ge=100, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """Get counts of nearby resources grouped by type."""
    service = ResourceService(db)
    counts = await service.get_resource_counts_by_type(
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
    )
    return ResourceCountResponse(counts=counts)


=======
>>>>>>> origin/main
# Incident-specific resource endpoints
@router.get("/incidents/{incident_id}/nearby-resources", response_model=NearbyResourceListResponse)
async def get_incident_nearby_resources(
    incident_id: UUID,
    radius_meters: Optional[float] = Query(None, ge=100, le=10000),
    resource_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get nearby resources for a specific incident."""
    # Verify incident exists
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found"
        )
    
    # Validate resource_type if provided
    if resource_type:
        try:
            ResourceType(resource_type)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid resource type: {resource_type}"
            )
    
    # Validate status if provided
    if status:
        try:
            ResourceStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status: {status}"
            )
    
    service = ResourceService(db)
    nearby = await service.get_resources_for_incident(
        incident_id=incident_id,
        radius_meters=radius_meters,
        resource_type=resource_type,
        status=status,
        limit=limit,
    )
    
    # Apply offset manually
    paginated = nearby[offset:offset + limit]
    
    return NearbyResourceListResponse(
        resources=paginated,
        total=len(nearby),
        limit=limit,
        offset=offset,
    )


@router.get("/incidents/{incident_id}/nearby-resources/{type}", response_model=NearbyResourceListResponse)
async def get_incident_resources_by_type(
    incident_id: UUID,
    type: str,
    radius_meters: Optional[float] = Query(None, ge=100, le=10000),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get nearby resources of a specific type for an incident."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found"
        )
    
    try:
        infra_type = ResourceType(type)
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid resource type: {type}"
        )
    
    infra_status = None
    if status:
        try:
            infra_status = ResourceStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status: {status}"
            )
    
    service = ResourceService(db)
    nearby = await service.get_resources_by_type(
        latitude=incident.centroid_latitude,
        longitude=incident.centroid_longitude,
        resource_type=type,
        radius_meters=radius_meters,
        status=status,
        limit=limit,
    )
    
    return NearbyResourceListResponse(
        infrastructure=nearby,
        total=len(nearby),
        limit=limit,
        offset=0,
    )


@router.get("/incidents/{incident_id}/resource-counts", response_model=ResourceCountResponse)
async def get_incident_resource_counts(
    incident_id: UUID,
    radius_meters: Optional[float] = Query(None, ge=100, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """Get counts of nearby resources by type for an incident."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found"
        )
    
    service = ResourceService(db)
    counts = await service.get_resource_counts_for_incident(incident_id, radius_meters)
    return ResourceCountResponse(counts=counts)


# Resource GeoJSON endpoint for map visualization
@router.get("/{resource_id}/geojson")
async def get_resource_geojson(
    resource_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single resource as GeoJSON."""
    service = ResourceService(db)
    resource = await service.get_resource_by_id(resource_id)
    if not resource:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Resource {resource_id} not found"
        )
    
    geojson = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [resource.longitude, resource.latitude]
        },
        "properties": {
            "id": str(resource.id),
            "name": resource.name,
            "type": resource.resource_type.value,
            "status": resource.status.value,
            "address": resource.address,
            "capacity": resource.capacity,
            "current_load": resource.current_load,
            "organization": resource.organization,
        }
    }
    return geojson


# Bulk status update for development/testing
@router.post("/bulk-status-update", response_model=dict)
async def bulk_update_status(
    resource_ids: List[UUID],
    status: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(require_role(["dispatcher", "commander", "admin"])),
):
    """Bulk update status for multiple resources (development/testing only)."""
    try:
        ResourceStatus(status)
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status: {status}"
        )
    
    service = ResourceService(db)
    updated = 0
    for resource_id in resource_ids:
        resource = await service.update_resource_status(resource_id, status)
        if resource:
            updated += 1
    
    return {"updated": updated, "total": len(resource_ids)}