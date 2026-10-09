from typing import Optional, List
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from geoalchemy2.functions import ST_AsGeoJSON

from app.database import get_db
from app.models.infrastructure import Infrastructure, InfrastructureType, InfrastructureStatus
from app.models.incident import Incident
from app.schemas.geospatial import (
    InfrastructureCreate,
    InfrastructureResponse,
    NearbyInfrastructureListResponse,
    AffectedInfrastructureSummaryResponse,
    IncidentLocationResponse,
    IncidentAnalysisAreaResponse,
    MapDataResponse,
    InfrastructureCountResponse,
)
from app.services.geospatial_service import GeospatialService

router = APIRouter(prefix="/incidents", tags=["geospatial"])


# Infrastructure CRUD endpoints
@router.post("/infrastructure", response_model=InfrastructureResponse, status_code=status.HTTP_201_CREATED)
async def create_infrastructure(
    infrastructure: InfrastructureCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new infrastructure record."""
    from geoalchemy2 import WKTElement
    from geoalchemy2.functions import ST_SetSRID, ST_MakePoint

    point = ST_SetSRID(ST_MakePoint(infrastructure.longitude, infrastructure.latitude), 4326)

    db_infra = Infrastructure(
        name=infrastructure.name,
        infrastructure_type=infrastructure.infrastructure_type,
        latitude=infrastructure.latitude,
        longitude=infrastructure.longitude,
        location=point,
        address=infrastructure.address,
        capacity=infrastructure.capacity,
        status=infrastructure.status,
        road_status=infrastructure.road_status,
        metadata=infrastructure.metadata or {},
    )

    db.add(db_infra)
    await db.commit()
    await db.refresh(db_infra)
    return db_infra


@router.get("/infrastructure", response_model=List[InfrastructureResponse])
async def list_infrastructure(
    infrastructure_type: Optional[InfrastructureType] = Query(None),
    status: Optional[InfrastructureStatus] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List infrastructure with optional filters."""
    query = select(Infrastructure)

    if infrastructure_type:
        query = query.where(Infrastructure.infrastructure_type == infrastructure_type)
    if status:
        query = query.where(Infrastructure.status == status)

    query = query.order_by(Infrastructure.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/infrastructure/{infrastructure_id}", response_model=InfrastructureResponse)
async def get_infrastructure(
    infrastructure_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific infrastructure by ID."""
    result = await db.execute(
        select(Infrastructure).where(Infrastructure.id == infrastructure_id)
    )
    infra = result.scalar_one_or_none()
    if not infra:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Infrastructure {infrastructure_id} not found"
        )
    return infra


@router.delete("/infrastructure/{infrastructure_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_infrastructure(
    infrastructure_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete an infrastructure record."""
    result = await db.execute(
        select(Infrastructure).where(Infrastructure.id == infrastructure_id)
    )
    infra = result.scalar_one_or_none()
    if not infra:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Infrastructure {infrastructure_id} not found"
        )
    await db.delete(infra)
    await db.commit()


# Geospatial endpoints for incidents
@router.get("/{incident_id}/location", response_model=IncidentLocationResponse)
async def get_incident_location(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get incident location with analysis radius."""
    result = await db.execute(
        select(Incident.centroid_latitude, Incident.centroid_longitude)
        .where(Incident.id == incident_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found"
        )
    return IncidentLocationResponse(
        incident_id=incident_id,
        latitude=row[0],
        longitude=row[1],
        analysis_radius_meters=1000.0,  # Default, could come from config
    )


@router.get("/{incident_id}/area", response_model=IncidentAnalysisAreaResponse)
async def get_incident_area(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get incident analysis area (buffer polygon)."""
    # Verify incident exists
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found"
        )

    service = GeospatialService(db)
    area = await service.get_analysis_area(incident_id)

    geometry = None
    if area:
        result = await db.execute(select(ST_AsGeoJSON(area.geometry)))
        geometry = result.scalar()

    return IncidentAnalysisAreaResponse(
        incident_id=incident_id,
        radius_meters=area.radius_meters if area else 1000.0,
        geometry=geometry,
        created_at=area.created_at if area else datetime.utcnow(),
    )


@router.post("/{incident_id}/area", response_model=IncidentAnalysisAreaResponse, status_code=status.HTTP_201_CREATED)
async def create_incident_area(
    incident_id: UUID,
    radius_meters: Optional[float] = Query(None, ge=100, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """Create or update the analysis area for an incident."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found"
        )

    service = GeospatialService(db)
    area = await service.create_analysis_area(incident_id, radius_meters)

    result = await db.execute(select(ST_AsGeoJSON(area.geometry)))
    geometry = result.scalar()

    return IncidentAnalysisAreaResponse(
        incident_id=incident_id,
        radius_meters=area.radius_meters,
        geometry=geometry,
        created_at=area.created_at,
    )


@router.get("/{incident_id}/infrastructure", response_model=NearbyInfrastructureListResponse)
async def get_nearby_infrastructure(
    incident_id: UUID,
    radius_meters: Optional[float] = Query(None, ge=100, le=10000),
    infrastructure_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get nearby infrastructure for an incident."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found"
        )

    # Parse infrastructure_type and status if provided
    infra_type = None
    if infrastructure_type:
        try:
            infra_type = InfrastructureType(infrastructure_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid infrastructure type: {infrastructure_type}"
            )

    infra_status = None
    if status:
        try:
            infra_status = InfrastructureStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status: {status}"
            )

    service = GeospatialService(db)
    nearby = await service.get_nearby_infrastructure(
        incident_id=incident_id,
        radius_meters=radius_meters,
        infrastructure_type=infra_type,
        status=infra_status,
        limit=limit,
    )

    # Apply offset manually since we're doing it in Python
    paginated = nearby[offset:offset + limit]

    return NearbyInfrastructureListResponse(
        infrastructure=paginated,
        total=len(nearby),
        limit=limit,
        offset=offset,
    )


@router.get("/{incident_id}/infrastructure/{type}", response_model=NearbyInfrastructureListResponse)
async def get_infrastructure_by_type(
    incident_id: UUID,
    type: str,
    radius_meters: Optional[float] = Query(None, ge=100, le=10000),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get nearby infrastructure of a specific type."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found"
        )

    try:
        infra_type = InfrastructureType(type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid infrastructure type: {type}"
        )

    infra_status = None
    if status:
        try:
            infra_status = InfrastructureStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status: {status}"
            )

    service = GeospatialService(db)
    nearby = await service.get_nearby_by_type(
        incident_id=incident_id,
        infrastructure_type=infra_type,
        radius_meters=radius_meters,
        status=infra_status,
        limit=limit,
    )

    return NearbyInfrastructureListResponse(
        infrastructure=nearby,
        total=len(nearby),
        limit=limit,
        offset=0,
    )


@router.get("/{incident_id}/affected", response_model=AffectedInfrastructureSummaryResponse)
async def get_affected_infrastructure(
    incident_id: UUID,
    radius_meters: Optional[float] = Query(None, ge=100, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """Get categorized infrastructure within incident analysis area."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found"
        )

    service = GeospatialService(db)
    affected = await service.analyze_affected_infrastructure(incident_id, radius_meters)

    return AffectedInfrastructureSummaryResponse(**affected.__dict__)


@router.get("/{incident_id}/map-data", response_model=MapDataResponse)
async def get_incident_map_data(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get GeoJSON map data for incident visualization."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found"
        )

    service = GeospatialService(db)
    map_data = await service.get_incident_map_data(incident_id)
    return map_data


@router.get("/{incident_id}/infrastructure-counts", response_model=InfrastructureCountResponse)
async def get_infrastructure_counts(
    incident_id: UUID,
    radius_meters: Optional[float] = Query(None, ge=100, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """Get counts of nearby infrastructure grouped by type."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found"
        )

    service = GeospatialService(db)
    counts = await service.get_infrastructure_count_by_type(incident_id, radius_meters)
    return InfrastructureCountResponse(counts=counts)