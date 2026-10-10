import asyncio
import logging
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.elements import WKTElement

from ai.services.clustering_service import process_new_event
from app.config import settings
from app.live_events import event_connections
from app.models.event import Event
from app.models.incident import Incident, IncidentStatus
from app.schemas.event import EventCreate, EventResponse

logger = logging.getLogger(__name__)
_poll_lock = asyncio.Lock()


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if abs(value) >= 100_000_000_000 else value
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError, OverflowError):
            return None
    return _utc_naive(parsed)


def _usgs_event(feature: dict[str, Any]) -> EventCreate | None:
    properties = feature.get("properties") or {}
    coordinates = (feature.get("geometry") or {}).get("coordinates") or []
    if len(coordinates) < 2 or not feature.get("id"):
        return None
    longitude, latitude = coordinates[:2]
    occurred_at = _parse_datetime(properties.get("time"))
    if occurred_at is None:
        return None
    magnitude = properties.get("mag")
    place = properties.get("place") or "Location not reported"
    return EventCreate(
        source="usgs",
        external_id=str(feature["id"])[:255],
        event_type="earthquake",
        text_content=f"USGS reported a magnitude {magnitude} earthquake near {place}.",
        latitude=latitude,
        longitude=longitude,
        location_name=place[:200],
        timestamp=occurred_at,
        metadata={
            "feed": "USGS",
            "magnitude": magnitude,
            "depth_km": coordinates[2] if len(coordinates) > 2 else None,
            "alert": properties.get("alert"),
            "url": properties.get("url"),
            "felt_reports": properties.get("felt"),
        },
    )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(element: ElementTree.Element, names: set[str]) -> str | None:
    for child in element.iter():
        if _local_name(child.tag) in names and child.text:
            return child.text.strip()
    return None


def _geojson_centroid(geometry: dict[str, Any]) -> tuple[float, float] | None:
    coordinates = geometry.get("coordinates")
    if geometry.get("type") == "Point" and isinstance(coordinates, list) and len(coordinates) >= 2:
        return float(coordinates[0]), float(coordinates[1])

    points: list[tuple[float, float]] = []

    def collect(value: Any) -> None:
        if (
            isinstance(value, (list, tuple))
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            points.append((float(value[0]), float(value[1])))
        elif isinstance(value, (list, tuple)):
            for nested in value:
                collect(nested)

    collect(coordinates)
    if not points:
        return None
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


def _gdacs_event(
    external_id: str,
    event_type: str,
    title: str,
    description: str,
    latitude: float,
    longitude: float,
    timestamp: datetime,
    link: str | None = None,
    alert_level: str | None = None,
) -> EventCreate:
    kind = {"FL": "flood", "TC": "cyclone", "WF": "wildfire"}[event_type.upper()]
    return EventCreate(
        source="gdacs",
        external_id=external_id[:255],
        event_type=kind,
        text_content=(description or title or f"GDACS {kind} alert")[:4000],
        latitude=latitude,
        longitude=longitude,
        location_name=(title or f"GDACS {kind} alert")[:200],
        timestamp=timestamp,
        metadata={
            "feed": "GDACS",
            "alert_level": alert_level,
            "url": link,
            "title": title,
        },
    )


def _gdacs_geojson_events(payload: dict[str, Any]) -> list[EventCreate]:
    events = []
    for feature in payload.get("features", []):
        properties = feature.get("properties") or {}
        event_type = str(
            properties.get("eventtype") or properties.get("event_type") or ""
        ).upper()
        if event_type not in {"FL", "TC", "WF"}:
            continue
        centroid = _geojson_centroid(feature.get("geometry") or {})
        timestamp = _parse_datetime(
            properties.get("fromdate")
            or properties.get("fromDate")
            or properties.get("date")
            or properties.get("timestamp")
        )
        external_id = (
            properties.get("eventid")
            or properties.get("eventId")
            or properties.get("id")
            or feature.get("id")
        )
        if centroid is None or timestamp is None or external_id is None:
            continue
        events.append(
            _gdacs_event(
                str(external_id),
                event_type,
                str(properties.get("eventname") or properties.get("name") or ""),
                str(properties.get("description") or ""),
                centroid[1],
                centroid[0],
                timestamp,
                properties.get("url") or properties.get("link"),
                properties.get("alertlevel") or properties.get("alertLevel"),
            )
        )
    return events


def _gdacs_rss_events(document: bytes) -> list[EventCreate]:
    root = ElementTree.fromstring(document)
    events = []
    for item in root.iter():
        if _local_name(item.tag) != "item":
            continue
        event_type = (_child_text(item, {"eventtype"}) or "").upper()
        external_id = (
            _child_text(item, {"eventid", "episodeid"})
            or _child_text(item, {"guid"})
        )
        title = _child_text(item, {"title"}) or ""
        description = _child_text(item, {"description"}) or ""
        link = _child_text(item, {"link"})
        timestamp = _parse_datetime(
            _child_text(item, {"pubdate", "fromdate", "date"})
        )
        point = _child_text(item, {"point"})
        latitude = _child_text(item, {"lat", "latitude"})
        longitude = _child_text(item, {"long", "lon", "longitude"})
        if point:
            pieces = point.replace(",", " ").split()
            if len(pieces) >= 2:
                latitude, longitude = pieces[:2]
        if (
            event_type not in {"FL", "TC", "WF"}
            or not external_id
            or timestamp is None
            or latitude is None
            or longitude is None
        ):
            continue
        try:
            lat_value = float(latitude)
            lon_value = float(longitude)
        except ValueError:
            continue
        events.append(
            _gdacs_event(
                external_id,
                event_type,
                title,
                description,
                lat_value,
                lon_value,
                timestamp,
                link,
                _child_text(item, {"alertlevel"}),
            )
        )
    return events


class ExternalIngestionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def poll(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "inserted": 0,
            "duplicates": 0,
            "cluster_errors": [],
            "sources": {},
        }
        headers = {"User-Agent": "RESQ-AI/0.1 external disaster data ingestion"}
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            await self._poll_source(
                result,
                "usgs",
                lambda: self._fetch_usgs(client),
            )
            await self._poll_source(
                result,
                "gdacs",
                lambda: self._fetch_gdacs(client),
            )
            if settings.OPENWEATHERMAP_API_KEY:
                await self._poll_source(
                    result,
                    "openweathermap",
                    lambda: self._fetch_weather(client),
                )
            else:
                result["sources"]["openweathermap"] = {
                    "status": "disabled",
                    "reason": "OPENWEATHERMAP_API_KEY is not configured.",
                    "inserted": 0,
                    "duplicates": 0,
                }
        return result

    async def _poll_source(
        self,
        result: dict[str, Any],
        source: str,
        fetch_events: Any,
    ) -> None:
        source_result = {"status": "ok", "inserted": 0, "duplicates": 0}
        result["sources"][source] = source_result
        try:
            events = await fetch_events()
            for event_data in events:
                created = await self._store_and_cluster(event_data, result)
                if created:
                    source_result["inserted"] += 1
                    result["inserted"] += 1
                else:
                    source_result["duplicates"] += 1
                    result["duplicates"] += 1
        except (httpx.HTTPError, ValueError, ElementTree.ParseError) as exc:
            error = self._safe_error(exc)
            logger.error("External ingestion failed for %s: %s", source, error)
            source_result["status"] = "error"
            source_result["error"] = error

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        if isinstance(exc, httpx.HTTPStatusError):
            return f"Feed returned HTTP {exc.response.status_code}."
        if isinstance(exc, httpx.HTTPError):
            return f"Feed request failed ({type(exc).__name__})."
        return str(exc)[:300]

    async def _fetch_usgs(self, client: httpx.AsyncClient) -> list[EventCreate]:
        response = await client.get(settings.USGS_SIGNIFICANT_FEED_URL)
        response.raise_for_status()
        payload = response.json()
        return [
            event
            for feature in payload.get("features", [])
            if (event := _usgs_event(feature)) is not None
        ]

    async def _fetch_gdacs(self, client: httpx.AsyncClient) -> list[EventCreate]:
        response = await client.get(settings.GDACS_FEED_URL)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "json" in content_type or response.content.lstrip().startswith(b"{"):
            return _gdacs_geojson_events(response.json())
        return _gdacs_rss_events(response.content)

    async def _fetch_weather(self, client: httpx.AsyncClient) -> list[EventCreate]:
        incidents = (
            await self.db.execute(
                select(Incident).where(
                    Incident.status != IncidentStatus.RESOLVED,
                    Incident.centroid_latitude.is_not(None),
                    Incident.centroid_longitude.is_not(None),
                )
            )
        ).scalars().all()
        events = []
        for incident in incidents:
            response = await client.get(
                settings.OPENWEATHERMAP_API_URL,
                params={
                    "lat": incident.centroid_latitude,
                    "lon": incident.centroid_longitude,
                    "appid": settings.OPENWEATHERMAP_API_KEY,
                    "units": "metric",
                    "exclude": "minutely,hourly,daily",
                },
            )
            response.raise_for_status()
            current = response.json().get("current") or {}
            alerts = response.json().get("alerts") or []
            rain_mm = float((current.get("rain") or {}).get("1h", 0) or 0)
            snow_mm = float((current.get("snow") or {}).get("1h", 0) or 0)
            wind_mps = float(current.get("wind_speed", 0) or 0)
            severe_alerts = [
                alert
                for alert in alerts
                if str(alert.get("event", "")).strip()
            ]
            if not severe_alerts and rain_mm < 10 and snow_mm < 10 and wind_mps < 17.2:
                continue

            observed_at = _parse_datetime(current.get("dt")) or datetime.now(
                timezone.utc
            ).replace(tzinfo=None)
            hour_key = int(
                observed_at.replace(minute=0, second=0, microsecond=0)
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
            descriptions = [
                f"{alert.get('event', 'Severe weather')}: {alert.get('description', '')}".strip()
                for alert in severe_alerts
            ]
            description = "; ".join(descriptions)
            if not description:
                description = (
                    f"Severe weather near {incident.title}: precipitation {rain_mm + snow_mm:g} mm/h, "
                    f"wind {wind_mps:g} m/s."
                )
            lowered = description.lower()
            kind = (
                "flood"
                if rain_mm >= 10 or snow_mm >= 10 or "flood" in lowered
                else "cyclone"
                if wind_mps >= 17.2
                else "severe_weather"
            )
            events.append(
                EventCreate(
                    source="openweathermap",
                    external_id=f"{incident.id}:{hour_key}",
                    event_type=kind,
                    text_content=description[:4000],
                    latitude=incident.centroid_latitude,
                    longitude=incident.centroid_longitude,
                    location_name=incident.title[:200],
                    timestamp=observed_at,
                    metadata={
                        "feed": "OpenWeatherMap",
                        "incident_id": str(incident.id),
                        "precipitation_mm_1h": rain_mm,
                        "snow_mm_1h": snow_mm,
                        "wind_speed_mps": wind_mps,
                        "alerts": severe_alerts,
                    },
                )
            )
        return events

    async def _store_and_cluster(
        self,
        event_data: EventCreate,
        result: dict[str, Any],
    ) -> bool:
        duplicate = await self._find_duplicate(event_data)
        if duplicate:
            return False

        event = Event(
            source=event_data.source,
            external_id=event_data.external_id,
            text_content=event_data.text_content,
            event_type=event_data.event_type,
            latitude=event_data.latitude,
            longitude=event_data.longitude,
            location=WKTElement(
                f"POINT({event_data.longitude} {event_data.latitude})",
                srid=4326,
            ),
            location_name=event_data.location_name,
            timestamp=event_data.timestamp,
            image_url=event_data.image_url,
            video_url=event_data.video_url,
            metadata=event_data.metadata or {},
        )
        self.db.add(event)
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            if await self._find_duplicate(event_data):
                return False
            raise
        await self.db.refresh(event)

        try:
            await process_new_event(event.id, self.db)
        except Exception as exc:
            logger.exception("Clustering failed for ingested event %s.", event.id)
            result["cluster_errors"].append(
                {"event_id": str(event.id), "error": str(exc)}
            )

        response = EventResponse.model_validate(event)
        await event_connections.broadcast(
            {"type": "event.created", "event": response.model_dump(mode="json")}
        )
        return True

    async def _find_duplicate(self, event_data: EventCreate) -> Event | None:
        if event_data.external_id:
            existing = await self.db.execute(
                select(Event).where(
                    Event.source == event_data.source,
                    Event.external_id == event_data.external_id,
                )
            )
            duplicate = existing.scalar_one_or_none()
            if duplicate is not None:
                return duplicate

        time_window = timedelta(minutes=5)
        location_tolerance = 0.0001
        existing = await self.db.execute(
            select(Event)
            .where(
                Event.source == event_data.source,
                Event.timestamp.between(
                    event_data.timestamp - time_window,
                    event_data.timestamp + time_window,
                ),
                Event.latitude.between(
                    event_data.latitude - location_tolerance,
                    event_data.latitude + location_tolerance,
                ),
                Event.longitude.between(
                    event_data.longitude - location_tolerance,
                    event_data.longitude + location_tolerance,
                ),
            )
            .limit(1)
        )
        return existing.scalar_one_or_none()


async def poll_external_feeds(db: AsyncSession) -> dict[str, Any]:
    async with _poll_lock:
        return await ExternalIngestionService(db).poll()
