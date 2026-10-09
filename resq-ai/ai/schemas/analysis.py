from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator
from uuid import UUID


DisasterType = Literal[
    "flood",
    "wildfire",
    "earthquake",
    "landslide",
    "cyclone",
    "tornado",
    "volcanic_activity",
    "building_collapse",
    "road_blockage",
    "tsunami",
    "hurricane",
    "storm",
    "explosion",
    "chemical_spill",
    "other",
]


class DisasterAnalysis(BaseModel):
    disaster_type: Optional[DisasterType] = None
    disaster_type_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    severity_indicators: List[str] = Field(default_factory=list)
    location_mentions: List[str] = Field(default_factory=list)
    damage_observed: List[str] = Field(default_factory=list)
    people_affected: Optional[str] = None
    vehicles_observed: List[str] = Field(default_factory=list)
    infrastructure_damage: List[str] = Field(default_factory=list)
    environmental_conditions: List[str] = Field(default_factory=list)
    summary: str = ""
    evidence_description: str = ""

    @field_validator("disaster_type_confidence", mode="before")
    @classmethod
    def validate_confidence(cls, v):
        if v is None:
            return None
        return max(0.0, min(1.0, float(v)))

    def merge_with(self, other: "DisasterAnalysis") -> "DisasterAnalysis":
        """Merge another analysis into this one, combining observations."""
        merged = DisasterAnalysis(
            disaster_type=self.disaster_type or other.disaster_type,
            disaster_type_confidence=max(
                self.disaster_type_confidence or 0.0,
                other.disaster_type_confidence or 0.0,
            ),
            severity_indicators=list(
                dict.fromkeys(self.severity_indicators + other.severity_indicators)
            ),
            location_mentions=list(
                dict.fromkeys(self.location_mentions + other.location_mentions)
            ),
            damage_observed=list(
                dict.fromkeys(self.damage_observed + other.damage_observed)
            ),
            people_affected=self.people_affected or other.people_affected,
            vehicles_observed=list(
                dict.fromkeys(self.vehicles_observed + other.vehicles_observed)
            ),
            infrastructure_damage=list(
                dict.fromkeys(self.infrastructure_damage + other.infrastructure_damage)
            ),
            environmental_conditions=list(
                dict.fromkeys(self.environmental_conditions + other.environmental_conditions)
            ),
            summary=self.summary or other.summary,
            evidence_description="; ".join(
                filter(None, [self.evidence_description, other.evidence_description])
            ),
        )
        return merged

    def to_dict(self) -> dict:
        return self.model_dump(exclude_none=True)


class EventAnalysisResponse(BaseModel):
    event_id: UUID
    analysis: DisasterAnalysis
    modality: str
    model_name: str
    created_at: datetime