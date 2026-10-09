# RESQ-AI — Multimodal Disaster Intelligence & Emergency Response Copilot

## Phase 0: Project Foundation ✓
## Phase 1: Data Ingestion ✓
## Phase 2: Multimodal AI Analysis ✓
## Phase 3: Incident Detection & Clustering ✓
## Phase 4: AI Evidence Investigation ✓
## Phase 5: Geospatial Intelligence ✓
## Phase 6: Dynamic Risk & Impact Assessment ✓

---

## Overview

RESQ-AI is an open-source disaster intelligence platform that ingests, validates, and stores multimodal disaster reports for further AI processing. Phase 4 implements an evidence-based investigation system that produces nuanced, traceable assessments of incident credibility.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌──────────────────┐
│   Frontend  │────▶│   Backend   │────▶│  PostgreSQL/     │
│   (React)   │     │  (FastAPI)  │     │  PostGIS         │
└─────────────┘     └─────────────┘     └──────────────────┘
                         │
                  ┌───────┴────────┐
                  │  AI Module     │
                  │  ┌──────────┐  │
                  │  │ Phase 2  │  │
                  │  │ Qwen2.5- │  │
                  │  │ VL       │  │
                  │  └──────────┘  │
                  │  ┌──────────┐  │
                  │  │ Phase 3  │  │
                  │  │ Incident │  │
                  │  │ Clustering│ │
                  │  └──────────┘  │
                  │  ┌──────────┐  │
                  │  │ Phase 4  │  │
                  │  │ Evidence │  │
                  │  │ Invest.  │  │
                  │  └──────────┘  │
                  │  ┌──────────┐  │
                  │  │ Phase 5  │  │
                  │  │ Geospatial│  │
                  │  └──────────┘  │
                  │  ┌──────────┐  │
                  │  │ Phase 6  │  │
                  │  │ Risk &   │  │
                  │  │ Impact   │  │
                  │  └──────────┘  │
                  └────────────────┘
```

## Phase 6: Dynamic Risk & Impact Assessment Flow

```
Incident (Phase 3/4/5)
        ↓
Phase 2 AI Analysis
        ↓
Phase 4 Evidence Investigation
        ↓
Phase 5 Geographic Intelligence
        ↓
Population Exposure + Infrastructure Exposure
        ↓
Environmental Conditions + Accessibility
        ↓
Risk & Impact Engine
        ↓
Risk Assessment + Impact Assessment
        ↓
Future Resource Optimization (Phase 7+)
```

## Project Structure

```
resq-ai/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── health.py               # Health check endpoint
│   │   │   ├── events.py               # Events CRUD endpoints
│   │   │   ├── analysis.py             # AI analysis endpoints
│   │   │   ├── incidents.py            # Incident endpoints (Phase 3)
│   │   │   ├── investigation.py        # Evidence investigation endpoints (Phase 4)
│   │   │   ├── geospatial.py           # Geospatial endpoints (Phase 5)
│   │   │   └── risk.py                 # Risk & Impact endpoints (Phase 6)
│   │   ├── models/
│   │   │   ├── event.py                # SQLAlchemy Event model (PostGIS)
│   │   │   ├── event_analysis.py       # AI Analysis model
│   │   │   ├── incident.py             # Incident model (Phase 3)
│   │   │   ├── evidence.py             # Evidence & Investigation models (Phase 4)
│   │   │   ├── infrastructure.py       # Infrastructure & Analysis Area models (Phase 5)
│   │   │   └── risk.py                 # Population zones, Risk & Impact models (Phase 6)
│   │   ├── schemas/
│   │   │   ├── event.py                # Pydantic validation schemas
│   │   │   ├── analysis.py             # AI analysis schemas
│   │   │   ├── incident.py             # Incident schemas (Phase 3)
│   │   │   ├── evidence.py             # Evidence investigation schemas (Phase 4)
│   │   │   ├── geospatial.py           # Geospatial schemas (Phase 5)
│   │   │   └── risk.py                 # Risk & Impact schemas (Phase 6)
│   │   ├── services/
│   │   │   ├── event_service.py        # Business logic
│   │   │   ├── geospatial_service.py   # Geospatial queries (Phase 5)
│   │   │   ├── risk_service.py         # Risk & Impact assessment (Phase 6)
│   │   │   └── event_service.py        # Event service (alias)
│   │   ├── config.py                   # Configuration (env-based)
│   │   ├── database.py                 # DB connection & session
│   │   └── main.py                     # FastAPI app entry point
│   └── pyproject.toml                  # Dependencies
├── ai/
│   ├── config.py                       # AI configuration
│   ├── models/
│   │   ├── base.py                     # Base model abstraction
│   │   ├── qwen_vl.py                  # Qwen2.5-VL implementation
│   │   ├── embedding_base.py           # Embedding model abstraction (Phase 3)
│   │   ├── sentence_transformer_embedding.py  # Embedding implementation (Phase 3)
│   │   └── __init__.py                 # Model factory & manager
│   ├── services/
│   │   ├── text_analyzer.py            # Text analysis
│   │   ├── image_analyzer.py           # Image analysis
│       ├── video_analyzer.py           # Video frame analysis
│       ├── multimodal_analyzer.py      # Multimodal fusion
│       ├── embedding_service.py        # Event embeddings (Phase 3)
│       ├── similarity_service.py       # Similarity calculations (Phase 3)
│       ├── clustering_service.py       # Incident clustering (Phase 3)
│       ├── evidence_collector.py       # Evidence collection (Phase 4)
│       └── evidence_investigator.py    # AI evidence investigator (Phase 4)
│   ├── schemas/
│       ├── analysis.py                 # DisasterAnalysis schema
│       └── evidence.py                 # Evidence schemas (Phase 4)
│   └── prompts/
│       ├── text_analysis.txt
│       ├── image_analysis.txt
│       ├── video_analysis.txt
│       └── evidence_investigation.txt  # Phase 4
├── database/                           # Future: migrations
├── data/
│   ├── sample_events.json              # 10 synthetic disaster reports
│   ├── load_sample_events.py           # Data loader script
│   ├── process_events.py               # Batch incident processing (Phase 3)
│   ├── load_test_scenarios.py          # Test data loader (Phase 3)
│   ├── test_scenarios.json             # Incident test scenarios (Phase 3)
│   ├── infrastructure.json             # Sample infrastructure data (Phase 5)
│   ├── load_infrastructure.py          # Infrastructure loader (Phase 5)
│   ├── test_texts/                     # Test text samples
│   ├── test_images/                    # Place test images here
│   └── test_videos/                    # Place test videos here
├── frontend/
│   ├── public/index.html
│   └── src/
│       ├── App.js                      # Main React component (with map view)
│       ├── App.css                     # Styles
│       ├── MapView.js                  # MapLibre GL component (Phase 5)
│       └── index.js                    # Entry point
├── tests/
│   ├── conftest.py                     # Pytest fixtures
│   ├── test_events.py                  # Event API tests
│   ├── test_ai_analysis.py             # AI service unit tests (mocked)
│   ├── test_analysis_api.py            # Analysis API integration tests
│   ├── test_incident_clustering.py     # Incident clustering tests (Phase 3)
│   ├── test_evidence_investigation.py  # Evidence investigation tests (Phase 4)
│   └── test_geospatial.py              # Geospatial tests (Phase 5)
├── docs/
│   ├── phase1-data-ingestion.md
│   ├── phase2-multimodal-ai.md
│   ├── phase3-incident-clustering.md
│   ├── phase4-evidence-investigation.md
│   └── phase5-geospatial-intelligence.md
├── docker/
├── .env.example                        # Environment template
├── .gitignore
└── README.md
```

---

## Database Schema

### Events Table

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, default gen_random_uuid() |
| source | VARCHAR(100) | NOT NULL, INDEX |
| text_content | TEXT | NULLABLE |
| event_type | VARCHAR(50) | NULLABLE, INDEX |
| latitude | FLOAT | NOT NULL, CHECK (-90 to 90) |
| longitude | FLOAT | NOT NULL, CHECK (-180 to 180) |
| location | GEOMETRY(POINT, 4326) | NOT NULL, GIST INDEX |
| location_name | VARCHAR(200) | NULLABLE |
| timestamp | TIMESTAMP | NOT NULL, INDEX (desc) |
| image_url | VARCHAR(500) | NULLABLE |
| video_url | VARCHAR(500) | NULLABLE |
| metadata | JSONB | DEFAULT '{}' |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() |

**PostGIS**: Uses `GEOMETRY(POINT, 4326)` for spatial queries with GIST index.

---

### Incident Table (Phase 3)

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, default gen_random_uuid() |
| incident_type | VARCHAR(50) | NULLABLE, INDEX |
| title | VARCHAR(500) | NOT NULL |
| summary | TEXT | NULLABLE |
| centroid_latitude | FLOAT | NULLABLE |
| centroid_longitude | FLOAT | NULLABLE |
| start_time | TIMESTAMP | NOT NULL, INDEX |
| last_updated | TIMESTAMP | NOT NULL, INDEX |
| event_count | INTEGER | DEFAULT 1 |
| status | ENUM | DEFAULT 'emerging' (emerging, active, resolved) |
| confidence | FLOAT | NULLABLE |
| created_at | TIMESTAMP | DEFAULT now() |
| updated_at | TIMESTAMP | DEFAULT now() |

### Incident-Event Relationship Table (Phase 3)

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, default gen_random_uuid() |
| incident_id | UUID | FOREIGN KEY → incidents.id, CASCADE |
| event_id | UUID | FOREIGN KEY → events.id, CASCADE |
| similarity_score | FLOAT | NULLABLE |
| geographic_distance_meters | FLOAT | NULLABLE |
| temporal_distance_minutes | FLOAT | NULLABLE |
| disaster_type_match | JSONB | NULLABLE |
| assignment_confidence | FLOAT | NULLABLE |
| relationship_components | JSONB | NULLABLE |
| created_at | TIMESTAMP | DEFAULT now() |

---

### Evidence Table (Phase 4)

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, default gen_random_uuid() |
| incident_id | UUID | FOREIGN KEY → incidents.id, CASCADE |
| event_id | UUID | FOREIGN KEY → events.id, SET NULL |
| evidence_type | ENUM | NOT NULL (text, image, video, geographic, temporal, multimodal, consistency, source_diversity) |
| evidence_role | ENUM | NOT NULL (supporting, contradicting, neutral, uncertain) |
| description | TEXT | NOT NULL |
| evidence_quality | FLOAT | NULLABLE (0-1) |
| confidence | FLOAT | NULLABLE (0-1) |
| source | VARCHAR(100) | NULLABLE |
| metadata | JSONB | DEFAULT '{}' |
| created_at | TIMESTAMP | DEFAULT now() |

### Incident Investigation Table (Phase 4)

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, default gen_random_uuid() |
| incident_id | UUID | FOREIGN KEY → incidents.id, CASCADE |
| supporting_evidence_count | INTEGER | DEFAULT 0 |
| contradicting_evidence_count | INTEGER | DEFAULT 0 |
| neutral_evidence_count | INTEGER | DEFAULT 0 |
| uncertain_evidence_count | INTEGER | DEFAULT 0 |
| evidence_confidence | FLOAT | NULLABLE (0-1) |
| assessment | ENUM | NOT NULL (strongly_supported, moderately_supported, weakly_supported, conflicting, insufficient_evidence, inconclusive) |
| explanation | TEXT | NULLABLE |
| limitations | TEXT | NULLABLE |
| source_diversity | FLOAT | NULLABLE |
| geographic_consistency | FLOAT | NULLABLE |
| temporal_consistency | FLOAT | NULLABLE |
| multimodal_consistency | FLOAT | NULLABLE |
| model_name | VARCHAR(200) | NULLABLE |
| investigated_at | TIMESTAMP | DEFAULT now() |
| created_at | TIMESTAMP | DEFAULT now() |

---

## Phase 2 API Endpoints

Base URL: `http://localhost:8000/api/v1`

### Analyze Event
```
POST /events/{event_id}/analyze
```

**Request Body (optional):**
```json
{
  "text": "Optional override text",
  "image_path": "/path/to/image.jpg",
  "video_path": "/path/to/video.mp4"
}
```

Uses event's existing text_content, image_url, video_url if not overridden.

**Response (201 Created):**
```json
{
  "id": "analysis-uuid",
  "event_id": "event-uuid",
  "modality": "text, image",
  "analysis": {
    "disaster_type": "flood",
    "disaster_type_confidence": 0.92,
    "severity_indicators": ["water rising rapidly", "vehicles stuck"],
    "location_mentions": ["city center", "main road"],
    "damage_observed": ["vehicles submerged", "road flooded"],
    "people_affected": "residents requesting rescue",
    "vehicles_observed": ["stuck vehicles"],
    "infrastructure_damage": ["main road flooded"],
    "environmental_conditions": ["heavy rain", "overcast"],
    "summary": "Heavy flooding on main road near city center...",
    "evidence_description": "Multimodal analysis (text, image): ..."
  },
  "model_name": "Qwen/Qwen2.5-VL-3B-Instruct",
  "created_at": "2026-09-21T12:00:00"
}
```

**Errors:**
- `404`: Event not found
- `422`: No analyzable content (event has no text, image, or video)

---

### Get Event Analysis
```
GET /events/{event_id}/analysis
```

Returns the latest stored analysis for the event. Does NOT run analysis automatically.

**Response (200 OK):** Same as analyze response above

**Response (404 Not Found):**
```json
{
  "detail": "No analysis found for event {id}. Run POST /events/{id}/analyze first."
}
```

---

## Phase 3 API Endpoints: Incident Clustering

Base URL: `http://localhost:8000/api/v1`

### Process Event for Incidents
```
POST /incidents/process-event/{event_id}
```

Processes an event and assigns it to an existing incident or creates a new one.

**Response (201 Created):**
```json
{
  "incident_id": "incident-uuid",
  "action": "created_new" | "added_to_existing",
  "relationship_score": 0.89,
  "incident_event_id": "incident-event-uuid",
  "components": {
    "semantic_similarity": 0.91,
    "geographic_score": 0.95,
    "temporal_score": 0.88,
    "disaster_type_score": 1.0
  }
}
```

### List Incidents
```
GET /incidents
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| status | string | - | Filter by status (emerging, active, resolved) |
| incident_type | string | - | Filter by incident type |
| start_date | datetime | - | Filter by start date |
| end_date | datetime | - | Filter by end date |
| limit | integer | 50 | Max results (1-100) |
| offset | integer | 0 | Pagination offset |

### Get Incident
```
GET /incidents/{incident_id}
```

Returns incident with all related events and relationship scores.

### Get Incident Events
```
GET /incidents/{incident_id}/events
```

Returns all events belonging to an incident.

### Batch Process Events
```
POST /incidents/batch-process
```

**Request Body:**
```json
{
  "event_ids": ["uuid1", "uuid2", ...],
  "limit": 100
}
```

**Response:**
```json
{
  "processed_events": 50,
  "new_incidents": 8,
  "updated_incidents": 42,
  "errors": []
}
```

---

## Phase 4 API Endpoints: Evidence Investigation

Base URL: `http://localhost:8000/api/v1`

### Run Investigation
```
POST /incidents/{incident_id}/investigate
```

**Request Body:**
```json
{
  "force_rerun": false
}
```

**Response (201 Created):**
```json
{
  "id": "investigation-uuid",
  "incident_id": "incident-uuid",
  "supporting_evidence_count": 5,
  "contradicting_evidence_count": 1,
  "neutral_evidence_count": 2,
  "uncertain_evidence_count": 1,
  "evidence_confidence": 0.78,
  "assessment": "moderately_supported",
  "explanation": "Supporting evidence (5 items) includes...",
  "limitations": "Limited source diversity...",
  "source_diversity": 0.6,
  "geographic_consistency": 0.9,
  "temporal_consistency": 0.85,
  "multimodal_consistency": 0.7,
  "model_name": "Qwen/Qwen2.5-VL-3B-Instruct",
  "investigated_at": "2026-09-21T12:00:00"
}
```

### Get Investigation
```
GET /incidents/{incident_id}/investigation
```

Returns stored investigation without re-running.

### Get Investigation Summary
```
GET /incidents/{incident_id}/investigation-summary
```

Returns detailed investigation with categorized evidence:
```json
{
  "incident_id": "incident-uuid",
  "supporting_evidence": [...],
  "contradicting_evidence": [...],
  "neutral_evidence": [...],
  "uncertain_evidence": [...],
  "source_diversity": 0.6,
  "geographic_consistency": 0.9,
  "temporal_consistency": 0.85,
  "multimodal_consistency": 0.7,
  "evidence_confidence_score": 0.78,
  "assessment": "moderately_supported",
  "explanation": "...",
  "limitations": "...",
  "model_name": "Qwen/Qwen2.5-VL-3B-Instruct",
  "investigated_at": "2026-09-21T12:00:00"
}
```

### Get Evidence
```
GET /incidents/{incident_id}/evidence
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| evidence_type | string | Filter by type |
| evidence_role | string | Filter by role |
| limit | integer | Max results |
| offset | integer | Pagination offset |

---

## Phase 5 API Endpoints: Geospatial Intelligence

Base URL: `http://localhost:8000/api/v1`

### Infrastructure CRUD

#### Create Infrastructure
```
POST /incidents/infrastructure
```

**Request Body:**
```json
{
  "name": "City Hospital",
  "infrastructure_type": "hospital",
  "latitude": 12.9716,
  "longitude": 77.5946,
  "address": "MG Road, Bengaluru",
  "capacity": 350,
  "status": "operational",
  "road_status": "open"
}
```

#### List Infrastructure
```
GET /incidents/infrastructure
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| type | string | Filter by infrastructure type |
| status | string | Filter by status |
| limit | integer | Max results (default 100) |
| offset | integer | Pagination offset |

#### Get Infrastructure
```
GET /incidents/infrastructure/{infrastructure_id}
```

#### Delete Infrastructure
```
DELETE /incidents/infrastructure/{infrastructure_id}
```

---

### Incident Geospatial Endpoints

#### Get Incident Location
```
GET /incidents/{incident_id}/location
```

Returns incident coordinates and default analysis radius.

#### Get/Manage Incident Analysis Area

**Get Analysis Area:**
```
GET /incidents/{incident_id}/area
```

Returns the analysis area polygon (GeoJSON) and radius.

**Create/Update Analysis Area:**
```
POST /incidents/{incident_id}/area?radius_meters=1500
```

Creates a PostGIS buffer polygon around the incident centroid.

---

### Nearby Infrastructure Queries

#### Get All Nearby Infrastructure
```
GET /incidents/{incident_id}/infrastructure
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| radius_meters | float | Search radius (default 1000, max 5000) |
| type | string | Filter by infrastructure type |
| status | string | Filter by status |
| limit | integer | Max results (default 100) |
| offset | integer | Pagination offset |

**Response (200 OK):**
```json
{
  "infrastructure": [
    {
      "id": "infra-uuid",
      "name": "City Hospital",
      "infrastructure_type": "hospital",
      "distance_meters": 245.3,
      "latitude": 12.9720,
      "longitude": 77.5950,
      "status": "operational",
      "capacity": 350,
      "address": "MG Road, Bengaluru",
      "road_status": "open",
      "metadata": {}
    }
  ],
  "total": 5,
  "limit": 100,
  "offset": 0
}
```

#### Get Infrastructure by Type
```
GET /incidents/{incident_id}/infrastructure/{type}
```

Examples: `/infrastructure/hospital`, `/infrastructure/shelter`, `/infrastructure/fire_station`

---

### Affected Infrastructure Analysis

```
GET /incidents/{incident_id}/affected
```

Returns categorized infrastructure within the incident analysis radius.

**Response:**
```json
{
  "hospitals_nearby": [...],
  "shelters_nearby": [...],
  "fire_stations_nearby": [...],
  "police_stations_nearby": [...],
  "schools_nearby": [...],
  "bridges_nearby": [...],
  "roads_nearby": [...],
  "emergency_centers_nearby": [...],
  "power_stations_nearby": [...],
  "water_facilities_nearby": [...],
  "total_count": 15
}
```

---

### Map Visualization

#### Get GeoJSON Map Data
```
GET /incidents/{incident_id}/map-data
```

Returns a complete GeoJSON FeatureCollection for map visualization:
- Incident point
- Analysis area polygon
- Nearby infrastructure points (categorized by type)

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    { "type": "Feature", "geometry": { "type": "Point", "coordinates": [77.5946, 12.9716] }, "properties": { "id": "...", "name": "Flood Incident", "type": "flood" } },
    { "type": "Feature", "geometry": { "type": "Polygon", ... }, "properties": { "name": "Analysis Area", "radius_meters": 1000 } },
    { "type": "Feature", "geometry": { "type": "Point", "coordinates": [77.5950, 12.9720] }, "properties": { "id": "...", "name": "City Hospital", "type": "hospital", "status": "operational", "distance_meters": 245 } }
  ]
}
```

---

### Infrastructure Counts

```
GET /incidents/{incident_id}/infrastructure-counts
```

Returns counts of nearby infrastructure grouped by type.

```json
{
  "counts": {
    "hospital": 2,
    "shelter": 3,
    "fire_station": 1,
    "police_station": 1,
    "road": 5,
    "bridge": 2
  }
}
```

---

## Phase 6 API Endpoints: Risk & Impact Assessment

Base URL: `http://localhost:8000/api/v1`

### Run Risk Assessment
```
POST /incidents/{incident_id}/risk-assessment
```

**Request Body (optional):**
```json
{
  "force_rerun": false
}
```

Runs risk and impact assessment for an incident.

**Response (201 Created):**
```json
{
  "id": "assessment-uuid",
  "incident_id": "incident-uuid",
  "risk_score": 74.5,
  "risk_level": "high",
  "severity_component": 82.3,
  "evidence_component": 65.1,
  "population_component": 91.2,
  "infrastructure_component": 45.7,
  "environment_component": 68.4,
  "accessibility_component": 32.1,
  "severity_details": {...},
  "evidence_details": {...},
  "population_details": {...},
  "infrastructure_details": {...},
  "environment_details": {...},
  "accessibility_details": {...},
  "explanation": "The assessment is elevated primarily because...",
  "model_name": "Qwen/Qwen2.5-VL-3B-Instruct",
  "assessed_at": "2026-09-21T12:00:00",
  "created_at": "2026-09-21T12:00:00"
}
```

**Errors:**
- `404`: Incident not found
- `422`: Invalid request

---

### Get Risk Assessment
```
GET /incidents/{incident_id}/risk-assessment
```

Returns the latest stored risk assessment for an incident.
Does NOT automatically run assessment - only returns stored results.

**Response (200 OK):** Same as analyze response above

**Response (404 Not Found):**
```json
{
  "detail": "No risk assessment found for incident {id}. Run POST /incidents/{id}/risk-assessment first."
}
```

---

### Recalculate Risk Assessment
```
POST /incidents/{incident_id}/risk-assessment/recalculate
```

Recalculates risk assessment using the latest available data.

**Response (201 Created):** Same as analyze response above

---

### Get Risk History
```
GET /incidents/{incident_id}/risk-history
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| limit | integer | 20 | Max results (1-100) |

**Response (200 OK):**
```json
[
  {
  "id": "history-uuid",
  "incident_id": "incident-uuid",
  "risk_score": 45.2,
  "risk_level": "moderate",
  "severity_component": 40.1,
  "evidence_component": 30.5,
  "population_component": 55.8,
  "infrastructure_component": 25.3,
  "environment_component": 15.2,
  "accessibility_component": 60.0,
  "explanation": "Initial assessment...",
  "trigger": "manual",
  "assessed_at": "2026-09-21T10:00:00"
  }
]
```

---

### Get Impact Assessment
```
GET /incidents/{incident_id}/impact
```

Returns the latest stored impact assessment for an incident.
Does NOT run assessment automatically.

**Response (200 OK):**
```json
{
  "id": "impact-uuid",
  "incident_id": "incident-uuid",
  "population_potentially_exposed": 12500,
  "population_zones_count": 3,
  "population_weighted_exposure": 8750.5,
  "infrastructure_potentially_exposed": 15,
  "hospitals_count": 2,
  "shelters_count": 3,
  "fire_stations_count": 1,
  "police_stations_count": 1,
  "schools_count": 0,
  "bridges_count": 2,
  "roads_count": 5,
  "emergency_centers_count": 1,
  "power_stations_count": 0,
  "water_facilities_count": 0,
  "roads_potentially_affected": 1,
  "bridges_potentially_affected": 0,
  "accessibility_status": "partially_blocked",
  "accessibility_details": {...},
  "explanation": "Incident analysis area contains 12,500 people...",
  "assessed_at": "2026-09-21T12:00:00"
}
```

**Response (404 Not Found):**
```json
{
  "detail": "No impact assessment found for incident {id}. Run POST /incidents/{id}/risk-assessment first."
}
```

---

### Recalculate Impact Assessment
```
POST /incidents/{incident_id}/impact/recalculate
```

Recalculates impact assessment using latest data.

**Response (201 Created):** Same as impact response above

---

## API Endpoints
```
GET /health
```
Response:
```json
{
  "status": "ok",
  "project": "RESQ-AI",
  "database": "connected"
}
```

---

### Create Event
```
POST /events
```
**Request Body:**
```json
{
  "source": "social_media",
  "text_content": "Heavy flooding reported near the city center",
  "event_type": "flood",
  "latitude": 12.9716,
  "longitude": 77.5946,
  "location_name": "Bengaluru",
  "timestamp": "2026-09-21T10:30:00",
  "image_url": null,
  "video_url": null,
  "metadata": {
    "platform": "synthetic",
    "author": "sample_user"
  }
}
```

**Validation Rules:**
- `source`: Required, non-empty string (max 100 chars)
- `text_content`: Optional if image_url or video_url provided
- `latitude`: Required, -90 to 90
- `longitude`: Required, -180 to 180
- `timestamp`: Required, valid ISO 8601 datetime
- `image_url`/`video_url`: Optional, must be valid HTTP/HTTPS URLs
- At least one of `text_content`, `image_url`, `video_url` must be provided

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "source": "social_media",
  "text_content": "Heavy flooding reported near the city center",
  "event_type": "flood",
  "latitude": 12.9716,
  "longitude": 77.5946,
  "location_name": "Bengaluru",
  "timestamp": "2026-09-21T10:30:00",
  "image_url": null,
  "video_url": null,
  "metadata": {"platform": "synthetic", "author": "sample_user"},
  "created_at": "2026-09-21T12:00:00",
  "updated_at": "2026-09-21T12:00:00"
}
```

---

### List Events
```
GET /events
```
**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| source | string | - | Filter by source |
| start_date | datetime | - | Filter by start date (ISO 8601) |
| end_date | datetime | - | Filter by end date (ISO 8601) |
| limit | integer | 50 | Max results (1-100) |
| offset | integer | 0 | Pagination offset |

**Response (200 OK):**
```json
{
  "events": [...],
  "total": 10,
  "limit": 50,
  "offset": 0
}
```

---

### Get Event by ID
```
GET /events/{event_id}
```
**Response (200 OK):** Single event object
**Response (404 Not Found):**
```json
{
  "detail": "Event with id 550e8400-e29b-41d4-a716-446655440000 not found"
}
```

---

### Delete Event
```
DELETE /events/{event_id}
```
**Response (200 OK):**
```json
{
  "message": "Event deleted successfully",
  "event_id": "550e8400-e29b-41d4-a716-446655440000"
}
```
**Response (404 Not Found):**
```json
{
  "detail": "Event with id 550e8400-e29b-41d4-a716-446655440000 not found"
}
```

---

## Validation Error Examples

### Invalid Latitude (422)
```json
{
  "detail": [
    {
      "type": "greater_than_equal",
      "loc": ["body", "latitude"],
      "msg": "Input should be greater than or equal to -90",
      "input": 200
    }
  ]
}
```

### Missing Required Field (422)
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "source"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

### Empty Source (422)
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "source"],
      "msg": "Source cannot be empty",
      "input": ""
    }
  ]
}
```

### Malformed URL (422)
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "image_url"],
      "msg": "URL must start with http:// or https://",
      "input": "not-a-url"
    }
  ]
}
```

### No Content or Media (422)
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body"],
      "msg": "At least one of text_content, image_url, or video_url must be provided",
      "input": {...}
    }
  ]
}
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ with PostGIS 3.4+
- **For AI inference**: GPU with 6GB+ VRAM (or CPU with 16GB+ RAM)

### 1. Clone & Setup Backend

```bash
cd resq-ai/backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies (includes AI dependencies)
pip install -e ".[dev,ai]"

# Configure environment
cp ../.env.example .env
# Edit .env with your database credentials and AI settings
# For CPU-only: AI_DEVICE=cpu
```

### 2. Start PostgreSQL with PostGIS

```bash
# Using Docker (recommended)
docker run -d \
  --name resq-ai-db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=resq_ai \
  -p 5432:5432 \
  postgis/postgis:15-3.4
```

### 3. Run Backend

```bash
cd resq-ai/backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend runs at: http://localhost:8000
API Docs: http://localhost:8000/docs

**Note**: The AI model loads on first analysis request (lazy loading). 
First request will take 30-120 seconds to download/load the model.
Subsequent requests are fast (model cached in memory).

### 4. Load Sample Data

```bash
cd resq-ai/data
python load_sample_events.py
```

### 5. Run Frontend

```bash
cd resq-ai/frontend
npm install
npm start
```

Frontend runs at: http://localhost:3000

**Frontend Map View**: Click the "Map" tab to view incidents with geographic context, analysis areas, and nearby infrastructure.

---

## Running Tests

### Unit Tests (Mocked AI - Fast)
```bash
cd resq-ai/backend
pytest tests/test_events.py tests/test_ai_analysis.py -v
```

### Integration Tests (Requires Model - Slow)
```bash
# Set environment variable to enable integration tests
AI_INTEGRATION_TESTS=1 pytest tests/test_analysis_api.py -v
```

### Test Coverage

```bash
pytest tests/ --cov=app --cov-report=term-missing
```

### Test Types
- **Unit tests** (`test_events.py`, `test_ai_analysis.py`): Use mocked AI responses, run in seconds, no GPU required
- **Integration tests** (`test_analysis_api.py`): Test full API flow with database, can optionally use real model

---

## Environment Variables

### Phase 0 & 1
| Variable | Description | Default |
|----------|-------------|---------|
| PROJECT_NAME | Project name | RESQ-AI |
| VERSION | Version | 0.1.0 |
| ENVIRONMENT | Environment | development |
| API_V1_PREFIX | API prefix | /api/v1 |
| DATABASE_HOST | PostgreSQL host | localhost |
| DATABASE_PORT | PostgreSQL port | 5432 |
| DATABASE_USER | PostgreSQL user | postgres |
| DATABASE_PASSWORD | PostgreSQL password | (required) |
| DATABASE_NAME | Database name | resq_ai |
| CORS_ORIGINS | Allowed origins | ["http://localhost:3000"] |

### Phase 2: AI Configuration
| Variable | Description | Default |
|----------|-------------|---------|
| AI_MODEL_NAME | HuggingFace model ID | Qwen/Qwen2.5-VL-3B-Instruct |
| AI_MODEL_REVISION | Model revision | main |
| AI_DEVICE | Device: auto, cuda, cpu, mps | auto |
| AI_DTYPE | Model dtype: auto, float16, bfloat16, float32 | auto |
| AI_MAX_MEMORY | Max GPU memory (e.g., '8GiB') | (none) |
| AI_OFFLOAD_FOLDER | CPU offload folder | (none) |
| AI_MAX_NEW_TOKENS | Max generation tokens | 1024 |
| AI_TEMPERATURE | Sampling temperature | 0.1 |
| AI_TOP_P | Top-p sampling | 0.9 |
| AI_DO_SAMPLE | Use sampling | false |
| VIDEO_FRAME_INTERVAL | Frame sample interval (seconds) | 5 |
| VIDEO_MAX_FRAMES | Max frames per video | 20 |
| MAX_IMAGE_SIZE | Max image dimension | 1024 |
| AI_INFERENCE_TIMEOUT | Inference timeout (seconds) | 300 |
| MODEL_LOAD_TIMEOUT | Model load timeout (seconds) | 120 |
| HF_CACHE_DIR | HuggingFace cache directory | (default) |

**Model Size Options:**
- `Qwen/Qwen2.5-VL-3B-Instruct` — ~6GB VRAM, good for consumer GPUs
- `Qwen/Qwen2.5-VL-7B-Instruct` — ~14GB VRAM, better accuracy
- `Qwen/Qwen2-VL-2B-Instruct` — ~4GB VRAM, fastest

---

### Phase 6: Risk Assessment Configuration
| Variable | Description | Default |
|----------|-------------|---------|
| RISK_WEIGHT_SEVERITY | Weight for severity component | 0.25 |
| RISK_WEIGHT_EVIDENCE | Weight for evidence component | 0.20 |
| RISK_WEIGHT_POPULATION | Weight for population component | 0.25 |
| RISK_WEIGHT_INFRASTRUCTURE | Weight for infrastructure component | 0.15 |
| RISK_WEIGHT_ENVIRONMENT | Weight for environment component | 0.10 |
| RISK_WEIGHT_ACCESSIBILITY | Weight for accessibility component | 0.05 |
| RISK_LEVEL_LOW_MAX | Max score for low risk | 19 |
| RISK_LEVEL_MODERATE_MAX | Max score for moderate risk | 39 |
| RISK_LEVEL_ELEVATED_MAX | Max score for elevated risk | 59 |
| RISK_LEVEL_HIGH_MAX | Max score for high risk | 79 |
| INFRA_WEIGHT_HOSPITAL | Hospital criticality weight | 10.0 |
| INFRA_WEIGHT_SHELTER | Shelter criticality weight | 8.0 |
| INFRA_WEIGHT_FIRE_STATION | Fire station criticality weight | 6.0 |
| INFRA_WEIGHT_POLICE_STATION | Police station criticality weight | 5.0 |
| INFRA_WEIGHT_BRIDGE | Bridge criticality weight | 7.0 |
| INFRA_WEIGHT_ROAD | Road criticality weight | 3.0 |
| INFRA_WEIGHT_EMERGENCY_CENTER | Emergency center criticality weight | 8.0 |
| INFRA_WEIGHT_POWER_STATION | Power station criticality weight | 6.0 |
| INFRA_WEIGHT_WATER_FACILITY | Water facility criticality weight | 6.0 |
| INFRA_WEIGHT_SCHOOL | School criticality weight | 4.0 |

---

## Phase 1 Design Decisions

1. **No AI Logic**: Phase 1 is pure data ingestion. AI processing (classification, risk scoring, etc.) comes in Phase 2.

2. **PostGIS Integration**: Geographic coordinates stored as `GEOMETRY(POINT, 4326)` enabling spatial queries (radius search, bounding box, etc.) for future phases.

3. **UUID Primary Keys**: Using UUIDs for distributed-friendly identifiers.

4. **JSONB Metadata**: Flexible metadata storage for source-specific fields without schema migrations.

5. **Service Layer Pattern**: Business logic separated from API layer for testability.

6. **Comprehensive Validation**: Pydantic v2 with field and model validators for clean error messages.

7. **Independent Tests**: Tests use in-memory SQLite, no external dependencies.

---

## Phase 2 Design Decisions

1. **Open-Source Only**: Uses Qwen2.5-VL family models via HuggingFace Transformers. No paid APIs.

2. **Configurable Model Size**: Switch between 2B, 3B, 7B variants via `.env` for different hardware.

3. **Model Abstraction**: `BaseMultimodalModel` interface allows swapping models without rewriting application code.

4. **Lazy Model Loading**: Model loads on first request, stays in memory for subsequent requests.

5. **Structured Output**: Prompts enforce JSON schema matching `DisasterAnalysis` Pydantic model.

6. **Multimodal Fusion**: Combines text/image/video analyses by merging unique observations, taking max confidence.

7. **Video Frame Sampling**: Configurable interval (default 5s) to balance accuracy vs compute.

8. **No Hallucination**: Prompts explicitly forbid inventing numbers/details not in input.

9. **Separation of Raw vs Analyzed**: Original events unchanged; AI results stored in separate `event_ai_analysis` table.

10. **Analysis on Demand**: POST to analyze, GET to retrieve. No auto-analysis on read.

11. **Comprehensive Mocking**: Unit tests use mocked models; integration tests can use real model.

12. **Device Auto-Detection**: Automatically uses CUDA, MPS, or CPU based on availability.

---

## Next Steps (Phase 3)

- Incident clustering (spatial/temporal grouping)
- Evidence investigation (cross-referencing sources)
- Misinformation detection
- Risk scoring
- Resource optimization
- Emergency response planning
- AI agents & RAG
