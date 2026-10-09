from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
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

    class Config:
        from_attributes = True


class EventAnalysisResponse(BaseModel):
    id: UUID
    event_id: UUID
    modality: str
    analysis: DisasterAnalysis
    model_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class AnalyzeEventRequest(BaseModel):
    text: Optional[str] = None
    image_path: Optional[str] = None
    video_path: Optional[str] = None