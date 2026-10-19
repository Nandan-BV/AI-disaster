from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Text, DateTime, Float, JSON, ForeignKey, Index, Integer, Enum as SQLEnum, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
import uuid
import enum

from app.database import Base


class ResourceType(str, enum.Enum):
    AMBULANCE = "ambulance"
    RESCUE_TEAM = "rescue_team"
    FIRE_VEHICLE = "fire_vehicle"
    POLICE_UNIT = "police_unit"
    SHELTER = "shelter"
    HOSPITAL = "hospital"
    DRONE = "drone"
    EMERGENCY_VEHICLE = "emergency_vehicle"


class ResourceStatus(str, enum.Enum):
    AVAILABLE = "available"
    DEPLOYED = "deployed"
    UNAVAILABLE = "unavailable"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class Resource(Base):
    __tablename__ = "resources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False)
    resource_type = Column(SQLEnum(ResourceType), nullable=False, index=True)
    status = Column(SQLEnum(ResourceStatus), default=ResourceStatus.UNKNOWN, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    address = Column(Text, nullable=True)
    capacity = Column(Integer, nullable=True)  # e.g., patient capacity for ambulance, people capacity for shelter
    current_load = Column(Integer, nullable=True)  # current utilization
    capabilities = Column(JSON, nullable=True, default=dict)  # flexible JSON capabilities
    organization = Column(String(200), nullable=True)  # e.g., "Fire Department", "EMS", "Police"
    metadata = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_resources_type_status", "resource_type", "status"),
        Index("ix_resources_location", "location", postgresql_using="gist"),
        CheckConstraint("capacity IS NULL OR capacity >= 0", name="ck_resources_capacity_non_negative"),
        CheckConstraint("current_load IS NULL OR current_load >= 0", name="ck_resources_current_load_non_negative"),
        CheckConstraint(
            "capacity IS NULL OR current_load IS NULL OR current_load <= capacity",
            name="ck_resources_current_load_not_exceed_capacity"
        ),
    )

    def __repr__(self):
        return f"<Resource(id={self.id}, name={self.name}, type={self.resource_type}, status={self.status})>"