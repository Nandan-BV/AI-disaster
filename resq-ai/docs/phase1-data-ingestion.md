# Phase 1: Data Ingestion — Architecture & Design

## Overview

Phase 1 implements the foundational data ingestion pipeline for RESQ-AI. It provides a clean, validated, and tested API for creating, retrieving, and managing disaster event reports from multiple sources.

**Scope**: Pure data ingestion — no AI processing, classification, or analysis.

---

## Design Principles

### 1. Separation of Concerns

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer (FastAPI)                      │
│  /api/v1/events  ──▶  Request validation  ──▶  Response        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Service Layer (Business Logic)              │
│  EventService  ──▶  CRUD operations  ──▶  DB abstraction       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Layer (SQLAlchemy + PostGIS)          │
│  Event Model  ──▶  PostgreSQL/PostGIS  ──▶  Persistence        │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Validation First

All input validation happens at the API boundary using Pydantic v2:
- Field-level validators (latitude, longitude, URLs)
- Model-level validators (at least one content field)
- Clear, actionable error messages

### 3. PostGIS-First Geographic Data

Coordinates stored as:
- `latitude` / `longitude` (FLOAT) — for simple queries
- `location` (GEOMETRY(POINT, 4326)) — for spatial queries

This enables Phase 2+ features:
- Radius search: "events within 50km of point"
- Bounding box: "events in this map viewport"
- Spatial clustering: "group nearby events"

### 4. Extensible Metadata

`metadata` column (JSONB) stores source-specific data without migrations:
```json
{
  "platform": "twitter",
  "author": "user123",
  "verified": false,
  "retweet_count": 42
}
```

### 5. UUID Primary Keys

Using UUID v4 for:
- Distributed insertion (no coordination needed)
- No enumeration attacks
- Future microservice compatibility

---

## Database Schema Deep Dive

### Table: `events`

```sql
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(100) NOT NULL,
    text_content TEXT,
    event_type VARCHAR(50),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    location GEOMETRY(POINT, 4326) NOT NULL,
    location_name VARCHAR(200),
    timestamp TIMESTAMP NOT NULL,
    image_url VARCHAR(500),
    video_url VARCHAR(500),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX ix_events_source ON events(source);
CREATE INDEX ix_events_event_type ON events(event_type);
CREATE INDEX ix_events_timestamp_desc ON events(timestamp DESC);
CREATE INDEX ix_events_location ON events USING GIST(location);

-- Constraints
ALTER TABLE events ADD CONSTRAINT chk_latitude CHECK (latitude BETWEEN -90 AND 90);
ALTER TABLE events ADD CONSTRAINT chk_longitude CHECK (longitude BETWEEN -180 AND 180);
```

### Why PostGIS?

| Feature | Standard Lat/Lon | PostGIS |
|---------|------------------|---------|
| Distance queries | Manual Haversine | `ST_DWithin` |
| Bounding box | Manual bounds check | `ST_MakeEnvelope` |
| Spatial clustering | Application-level | `ST_ClusterDBSCAN` |
| SRID handling | Manual | Automatic |
| Performance | Table scans | GIST index |

---

## API Design

### RESTful Conventions

| Operation | Endpoint | Status Codes |
|-----------|----------|--------------|
| Create | `POST /events` | 201, 422 |
| List | `GET /events` | 200 |
| Get One | `GET /events/{id}` | 200, 404 |
| Delete | `DELETE /events/{id}` | 200, 404 |

### Request/Response Schemas

**EventCreate** (input):
- Strict validation, no extra fields allowed
- `source`: required, min 1 char
- `latitude`/`longitude`: range validated
- `timestamp`: ISO 8601 parsed
- URLs: must be http/https

**EventResponse** (output):
- Includes generated `id`, `created_at`, `updated_at`
- `from_attributes=True` for SQLAlchemy integration

**EventListResponse** (paginated):
- `events`: array of EventResponse
- `total`: total count (for pagination UI)
- `limit`/`offset`: echo of request params

---

## Validation Rules

| Field | Rules |
|-------|-------|
| `source` | Required, 1-100 chars, trimmed |
| `text_content` | Optional, trimmed, nullable |
| `event_type` | Optional, max 50 chars |
| `latitude` | Required, -90 to 90 |
| `longitude` | Required, -180 to 180 |
| `location_name` | Optional, max 200 chars |
| `timestamp` | Required, valid ISO 8601 |
| `image_url` | Optional, valid HTTP/HTTPS URL |
| `video_url` | Optional, valid HTTP/HTTPS URL |
| `metadata` | Optional, JSON object |
| **Cross-field** | At least one of: text_content, image_url, video_url |

---

## Error Handling

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success (GET, DELETE) |
| 201 | Created (POST) |
| 404 | Not Found (GET one, DELETE) |
| 422 | Validation Error (Pydantic) |
| 500 | Server Error (unexpected) |

### Validation Error Format

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "field_name"],
      "msg": "Human readable message",
      "input": "invalid_value"
    }
  ]
}
```

Frontend can map `loc[1]` to form fields for inline errors.

---

## Sample Data

### `data/sample_events.json`

10 synthetic disaster reports covering:
- Flood (2): Bengaluru, Srinagar
- Wildfire: Los Angeles
- Earthquake: Tokyo
- Landslide: Dehradun
- Cyclone: Nagpur
- Building Collapse: New Delhi
- Road Blockage: Mumbai
- Volcanic Activity: Krakatoa
- Tornado: Denver

All coordinates, timestamps, and content are fictional.

### Loader Script

`data/load_sample_events.py`:
- Reads JSON
- Creates tables if missing
- Inserts via SQLAlchemy (bypasses API for speed)
- Uses PostGIS `ST_MakePoint` for geometry

```bash
cd data
python load_sample_events.py
```

---

## Testing Strategy

### Test File: `tests/test_events.py`

**Test Classes:**
- `TestCreateEvent`: 9 tests (success + 8 validation failures)
- `TestGetEvents`: 4 tests (empty, with data, filter, pagination)
- `TestGetEventById`: 2 tests (success, not found)
- `TestDeleteEvent`: 2 tests (success, not found)
- `TestHealthEndpoint`: 1 test

**Fixtures:**
- `test_engine`: In-memory SQLite (session scope)
- `db_session`: Per-test session with rollback
- `client`: AsyncClient with overridden dependencies

**Run:**
```bash
cd backend
pytest tests/test_events.py -v
```

### Test Independence

Each test:
- Creates its own data
- Rolls back transaction
- No shared state
- Repeatable in any order

---

## Frontend Integration

### Simple Development Page

`frontend/src/App.js` provides:
- Backend connection status indicator
- Event submission form with all fields
- Real-time validation feedback
- Created event display (JSON)
- Events list with delete buttons

### API Proxy

`package.json` includes:
```json
"proxy": "http://localhost:8000"
```

This forwards `/api/*` to backend during development (`npm start`).

---

## Configuration

### Environment Variables (`.env`)

```bash
# Database (required)
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=your_secure_password
DATABASE_NAME=resq_ai

# Optional
ENVIRONMENT=development
CORS_ORIGINS=["http://localhost:3000"]
```

### CORS

Configured in `main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Dependencies Added

| Package | Version | Purpose |
|---------|---------|---------|
| geoalchemy2 | >=0.14.0 | PostGIS ORM support |
| (existing) | | FastAPI, SQLAlchemy, Pydantic, etc. |

No new runtime dependencies beyond Phase 0.

---

## Migration Path to Phase 2

Phase 1 events are ready for AI consumption:

1. **Polling**: `GET /events?start_date=...` for new events
2. **Webhooks**: Add `webhook_url` to metadata for push
3. **Message Queue**: Future: publish to Kafka/RabbitMQ on create
4. **Schema Extension**: Add AI fields via new columns or metadata:
   - `classification`, `confidence`, `risk_score` (new columns)
   - `ai_analysis` (JSONB in metadata)

---

## Security Considerations

- No authentication in Phase 1 (dev only)
- All secrets in `.env` (not committed)
- Input validation prevents injection
- CORS restricted to known origins
- DELETE endpoint for dev/testing only

---

## Performance Notes

- Connection pooling via SQLAlchemy async engine
- GIST index on `location` for spatial queries
- Composite index on `(timestamp DESC)` for recent events
- Pagination limits (max 100) prevent large payloads

---

## Future Enhancements (Post-Phase 1)

1. **Bulk Insert**: `POST /events/batch` for high-throughput sources
2. **Webhooks**: Push notifications on event creation
3. **GeoJSON Output**: `GET /events.geojson` for mapping
4. **Full-Text Search**: `text_content` search via `tsvector`
5. **Source Management**: CRUD for source configuration
6. **Rate Limiting**: Per-source quotas