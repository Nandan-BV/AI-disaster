from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Text, DateTime, Float, JSON, ForeignKey, Index, Integer, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
import uuid
import enum

from app.database import Base


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MODERATE = "moderate"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


class PopulationZone(Base):
    __tablename__ = "population_zones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False)
    population = Column(Integer, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    geometry = Column(Geometry(geometry_type="POLYGON", srid=4326), nullable=True)
    vulnerability_factor = Column(Float, default=0.5)  # 0-1 synthetic factor
    metadata = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_population_zones_location", "location", postgresql_using="gist"),
        Index("ix_population_zones_geometry", "geometry", postgresql_using="gist"),
    )

    def __repr__(self):
        return f"<PopulationZone(id={self.id}, name={self.name}, population={self.population})>"


class EnvironmentalConditions(Base):
    __tablename__ = "environmental_conditions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    temperature = Column(Float, nullable=True)  # Celsius
    rainfall = Column(Float, nullable=True)  # mm/h
    wind_speed = Column(Float, nullable=True)  # km/h
    humidity = Column(Float, nullable=True)  # percentage
    water_level = Column(Float, nullable=True)  # meters
    visibility = Column(Float, nullable=True)  # km
    weather_description = Column(String(200), nullable=True)
    metadata = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    incident = relationship("Incident", backref="environmental_conditions")

    __table_args__ = (
        Index("ix_env_conditions_incident_time", "incident_id", "timestamp"),
    )

    def __repr__(self):
        return f"<EnvironmentalConditions(incident={self.incident_id}, time={self.timestamp})>"


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    risk_score = Column(Float, nullable=False)  # 0-100
    risk_level = Column(SQLEnum(RiskLevel), nullable=False, index=True)
    
    # Component scores (0-100 each)
    severity_component = Column(Float, nullable=True)
    evidence_component = Column(Float, nullable=True)
    population_component = Column(Float, nullable=True)
    infrastructure_component = Column(Float, nullable=True)
    environment_component = Column(Float, nullable=True)
    accessibility_component = Column(Float, nullable=True)
    
    # Raw component values for transparency
    severity_details = Column(JSON, nullable=True)
    evidence_details = Column(JSON, nullable=True)
    population_details = Column(JSON, nullable=True)
    infrastructure_details = Column(JSON, nullable=True)
    environment_details = Column(JSON, nullable=True)
    accessibility_details = Column(JSON, nullable=True)
    
    explanation = Column(Text, nullable=True)
    model_name = Column(String(200), nullable=True)
    assessed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    incident = relationship("Incident", backref="risk_assessments")

    __table_args__ = (
        Index("ix_risk_assessments_incident_time", "incident_id", "assessed_at"),
    )

    def __repr__(self):
        return f"<RiskAssessment(incident={self.incident_id}, score={self.risk_score}, level={self.risk_level})>"


class ImpactAssessment(Base):
    __tablename__ = "impact_assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    population_potentially_exposed = Column(Integer, nullable=True)
    population_zones_count = Column(Integer, nullable=True)
    population_weighted_exposure = Column(Float, nullable=True)
    infrastructure_potentially_exposed = Column(Integer, nullable=True)
    hospitals_count = Column(Integer, nullable=True)
    shelters_count = Column(Integer, nullable=True)
    fire_stations_count = Column(Integer, nullable=True)
    police_stations_count = Column(Integer, nullable=True)
    schools_count = Column(Integer, nullable=True)
    bridges_count = Column(Integer, nullable=True)
    roads_count = Column(Integer, nullable=True)
    emergency_centers_count = Column(Integer, nullable=True)
    power_stations_count = Column(Integer, nullable=True)
    water_facilities_count = Column(Integer, nullable=True)
    roads_potentially_affected = Column(Integer, nullable=True)
    bridges_potentially_affected = Column(Integer, nullable=True)
    accessibility_status = Column(String(50), nullable=True)  # open, partially_blocked, blocked, unknown
    accessibility_details = Column(JSON, nullable=True)
    explanation = Column(Text, nullable=True)
    assessed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    incident = relationship("Incident", backref="impact_assessments")

    __table_args__ = (
        Index("ix_impact_assessments_incident_time", "incident_id", "assessed_at"),
    )

    def __repr__(self):
        return f"<ImpactAssessment(incident={self.incident_id}, population={self.population_potentially_exposed})>"


class RiskAssessmentHistory(Base):
    __tablename__ = "risk_assessment_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    risk_score = Column(Float, nullable=False)
    risk_level = Column(SQLEnum(RiskLevel), nullable=False)
    severity_component = Column(Float, nullable=True)
    evidence_component = Column(Float, nullable=True)
    population_component = Column(Float, nullable=True)
    infrastructure_component = Column(Float, nullable=True)
    environment_component = Column(Float, nullable=True)
    accessibility_component = Column(Float, nullable=True)
    explanation = Column(Text, nullable=True)
    trigger = Column(String(100), nullable=True)  # manual, auto, scheduled, environmental_change
    assessed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    incident = relationship("Incident", backref="risk_history")

    __table_args__ = (
        Index("ix_risk_history_incident_time", "incident_id", "assessed_at"),
    )

    def __repr__(self):
        return f"<RiskAssessmentHistory(incident={self.incident_id}, score={self.risk_score}, level={self.risk_level})>"


class DemandPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ResourceDemand(Base):
    __tablename__ = "resource_demands"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_type = Column(String(50), nullable=False, index=True)
    required_quantity = Column(Integer, nullable=False, default=1)
    priority = Column(SQLEnum(DemandPriority), nullable=False, default=DemandPriority.MEDIUM)
    minimum_capability = Column(JSON, nullable=True)  # Required capabilities as JSON
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    incident = relationship("Incident", backref="resource_demands")

    __table_args__ = (
        Index("ix_resource_demands_incident_type", "incident_id", "resource_type"),
    )

    def __repr__(self):
        return f"<ResourceDemand(incident={self.incident_id}, type={self.resource_type}, qty={self.required_quantity})>"


class OptimizationStatus(str, enum.Enum):
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    NO_SOLUTION = "no_solution"
    ERROR = "error"


class OptimizationResult(Base):
    __tablename__ = "optimization_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(SQLEnum(OptimizationStatus), nullable=False, index=True)
    objective_value = Column(Float, nullable=True)
    total_distance = Column(Float, nullable=True)
    total_resources = Column(Integer, nullable=True)
    unmet_demand = Column(JSON, nullable=True)  # Details of unmet demand
    explanation = Column(Text, nullable=True)
    solver_name = Column(String(100), nullable=True)
    solver_status = Column(String(50), nullable=True)  # OR-Tools solver status
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    incident = relationship("Incident", backref="optimization_results")
    allocations = relationship("ResourceAllocation", back_populates="optimization_result", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_optimization_results_incident_time", "incident_id", "created_at"),
    )

    def __repr__(self):
        return f"<OptimizationResult(incident={self.incident_id}, status={self.status}, obj={self.objective_value})>"


class AllocationStatus(str, enum.Enum):
    RECOMMENDED = "recommended"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ResourceAllocation(Base):
    __tablename__ = "resource_allocations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    optimization_result_id = Column(
        UUID(as_uuid=True),
        ForeignKey("optimization_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    demand_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resource_demands.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    resource_type = Column(String(50), nullable=False)
    distance_meters = Column(Float, nullable=True)
    assignment_score = Column(Float, nullable=True)  # Score from optimizer
    assignment_reason = Column(Text, nullable=True)
    status = Column(SQLEnum(AllocationStatus), nullable=False, default=AllocationStatus.RECOMMENDED, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    optimization_result = relationship("OptimizationResult", back_populates="allocations")
    incident = relationship("Incident", backref="resource_allocations")
    resource = relationship("Resource", backref="allocations")
    demand = relationship("ResourceDemand", backref="allocations")

    __table_args__ = (
        Index("ix_resource_allocations_opt_result", "optimization_result_id"),
        Index("ix_resource_allocations_incident_resource", "incident_id", "resource_id"),
    )

    def __repr__(self):
        return f"<ResourceAllocation(opt={self.optimization_result_id}, resource={self.resource_id}, status={self.status})>"


class OptimizationHistory(Base):
    __tablename__ = "optimization_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    optimization_result_id = Column(
        UUID(as_uuid=True),
        ForeignKey("optimization_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trigger = Column(String(100), nullable=True)  # manual, auto, recalculate, environmental_change
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    incident = relationship("Incident", backref="optimization_history")

    __table_args__ = (
        Index("ix_optimization_history_incident_time", "incident_id", "created_at"),
    )

    def __repr__(self):
        return f"<OptimizationHistory(incident={self.incident_id}, opt={self.optimization_result_id})>"