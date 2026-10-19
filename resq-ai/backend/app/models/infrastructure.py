from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Text, DateTime, Float, JSON, ForeignKey, Index, Integer, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
import uuid
import enum

from app.database import Base


class InfrastructureType(str, enum.Enum):
    HOSPITAL = "hospital"
    SHELTER = "shelter"
    FIRE_STATION = "fire_station"
    POLICE_STATION = "police_station"
    SCHOOL = "school"
    BRIDGE = "bridge"
    ROAD = "road"
    POWER_STATION = "power_station"
    WATER_FACILITY = "water_facility"
    EMERGENCY_CENTER = "emergency_center"


class InfrastructureStatus(str, enum.Enum):
    OPERATIONAL = "operational"
    PARTIALLY_OPERATIONAL = "partially_operational"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class RoadStatus(str, enum.Enum):
    OPEN = "open"
    PARTIALLY_BLOCKED = "partially_blocked"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class Infrastructure(Base):
    __tablename__ = "infrastructure"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False)
    infrastructure_type = Column(SQLEnum(InfrastructureType), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    address = Column(Text, nullable=True)
    capacity = Column(Integer, nullable=True)  # e.g., bed count for hospital, capacity for shelter
    status = Column(SQLEnum(InfrastructureStatus), default=InfrastructureStatus.UNKNOWN, nullable=False, index=True)
    road_status = Column(SQLEnum(RoadStatus), nullable=True)  # For roads/bridges
    metadata = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_infrastructure_type_status", "infrastructure_type", "status"),
        Index("ix_infrastructure_location", "location", postgresql_using="gist"),
    )

    def __repr__(self):
        return f"<Infrastructure(id={self.id}, name={self.name}, type={self.infrastructure_type}, status={self.status})>"


class IncidentAnalysisArea(Base):
    __tablename__ = "incident_analysis_areas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    geometry = Column(Geometry(geometry_type="POLYGON", srid=4326), nullable=False)
    radius_meters = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    incident = relationship("Incident", backref="analysis_area")

    __table_args__ = (
        Index("ix_incident_analysis_area_geometry", "geometry", postgresql_using="gist"),
    )

    def __repr__(self):
        return f"<IncidentAnalysisArea(incident_id={self.incident_id}, radius={self.radius_meters}m)>"