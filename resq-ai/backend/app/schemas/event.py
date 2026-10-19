from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from uuid import UUID
from typing import Any


class EventCreate(BaseModel):
    source: str = Field(..., min_length=1, max_length=100, description="Source of the event (e.g., social_media, news, satellite)")
    external_id: Optional[str] = Field(None, max_length=255, description="Stable identifier assigned by an external feed")
    text_content: Optional[str] = Field(None, description="Text description of the event")
    event_type: Optional[str] = Field(None, max_length=50, description="Type of disaster event")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")
    location_name: Optional[str] = Field(None, max_length=200, description="Human-readable location name")
    timestamp: datetime = Field(..., description="Event timestamp in ISO format")
    image_url: Optional[str] = Field(None, max_length=500, description="URL to event image")
    video_url: Optional[str] = Field(None, max_length=500, description="URL to event video")
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Source cannot be empty")
        return v.strip()

    @field_validator("image_url", "video_url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v = v.strip()
            if not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("URL must start with http:// or https://")
            return v
        return None

    @field_validator("text_content")
    @classmethod
    def validate_text_content(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip() if v.strip() else None
        return None

    @model_validator(mode="after")
    def validate_content_or_media(self) -> "EventCreate":
        if not self.text_content and not self.image_url and not self.video_url:
            raise ValueError("At least one of text_content, image_url, or video_url must be provided")
        return self


class EventResponse(BaseModel):
    id: UUID
    source: str
    external_id: Optional[str] = None
    text_content: Optional[str]
    event_type: Optional[str]
    latitude: float
    longitude: float
    location_name: Optional[str]
    timestamp: datetime
    image_url: Optional[str]
    video_url: Optional[str]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    events: list[EventResponse]
    total: int
    limit: int
    offset: int


class EventDeleteResponse(BaseModel):
    message: str
    event_id: UUID