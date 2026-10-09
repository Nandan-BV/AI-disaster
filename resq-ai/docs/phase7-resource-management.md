# Phase 7: Emergency Resource Management — Architecture & Design

## Overview

Phase 7 implements the emergency resource management layer for RESQ-AI. It provides a structured system for managing emergency resources such as ambulances, rescue teams, fire vehicles, police units, shelters, hospitals, drones, and emergency vehicles.

The system tracks:
- Resource location (PostGIS geospatial)
- Resource type and capabilities
- Current status (available, deployed, unavailable, maintenance, unknown)
- Capacity and current load
- Organization ownership
- Custom metadata

---

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌──────────────────┐
│   Frontend  │────▶│   Backend   │────▶│  PostgreSQL/     │
│   (React)   │     │  (FastAPI)  │     │  PostGIS         │
└─────────────┘     └─────────────┘     └──────────────────┘
                           │
                    ┌──────┴──────────────┐
                    │  Resources Module   │
                    │  ┌──────────────┐   │
                    │  │  CRUD        │   │
                    │  │  Geospatial  │   │
                    │  │  Status Mgmt │   │
                    │  │  Capabilities│   │
                    │  └──────────────┘   │
                    └─────────────────────┘
```

---

## Resource Data Model

### `resources` table

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, default gen_random_uuid() |
| name | VARCHAR(500) | NOT NULL |
| resource_type | ENUM | NOT NULL (ambulance, rescue_team, fire_vehicle, police_unit, shelter, hospital, drone, emergency_vehicle) |
| status | ENUM | NOT NULL, DEFAULT 'unknown' (available, deployed, unavailable, maintenance, unknown) |
| latitude | FLOAT | NOT NULL, CHECK (-90 to 90) |
| longitude | FLOAT | NOT NULL, CHECK (-180 to 180) |
| location | GEOMETRY(POINT, 4326) | NOT NULL, GIST INDEX |
| address | TEXT | NULLABLE |
| capacity | INTEGER | NULLABLE, CHECK (>= 0) |
| current_load | INTEGER | NULLABLE, CHECK (>= 0, <= capacity) |
| capabilities | JSONB | DEFAULT '{}' |
| organization | VARCHAR(200) | NULLABLE |
| metadata | JSONB | DEFAULT '{}' |
| created_at | TIMESTAMP | DEFAULT now() |
| updated_at | TIMESTAMP | DEFAULT now(), on update |

### Constraints
- `capacity >= 0`
- `current_load >= 0`
- `current_load <= capacity` (when both provided)
- Spatial index on `location` for fast geospatial queries

---

## Resource Types & Capabilities

### Supported Types
| Type | Example Capabilities |
|------|---------------------|
| ambulance | medical, trauma, water_rescue, night_operation |
| rescue_team | heavy_rescue, water_rescue, medical, rope_rescue, confined_space |
| fire_vehicle | fire_suppression, water_rescue, hazmat, high_rise |
| police_unit | traffic_control, crowd_management, security, emergency_response |
| shelter | overnight, food, medical_basic, wheelchair_accessible, pet_friendly |
| hospital | emergency, trauma, icu, surgery, maternity, pediatrics, burn_unit |
| drone | aerial_surveillance, thermal_imaging, night_vision, live_streaming, payload_delivery |
| emergency_vehicle | command_control, communications, medical_support, lighting, generator |

### Capabilities JSON Structure
```json
{
  "medical": true,
  "trauma": true,
  "water_rescue": false,
  "night_operation": true,
  "fire_suppression": false,
  "hazmat": false,
  "heavy_rescue": true
}
```

---

## Resource Status Lifecycle

```
available ──▶ deployed ──▶ available
    │           │
    │           ▼
    │      unavailable
    │           │
    ▼           ▼
maintenance ──▶ available
```

### Status Meanings
| Status | Meaning |
|--------|---------|
| available | Ready for deployment |
| deployed | Currently assigned to an incident |
| unavailable | Cannot be used (damage, staffing, etc.) |
| maintenance | Under repair/service |
| unknown | Status not reported/known |

---

## API Endpoints

### Base URL: `http://localhost:8000/api/v1`

### Resource CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/resources` | Create new resource |
| GET | `/resources` | List resources (with filters) |
| GET | `/resources/{id}` | Get resource by ID |
| PATCH | `/resources/{id}` | Update resource |
| PATCH | `/resources/{id}/status` | Update resource status |
| DELETE | `/resources/{id}` | Delete resource |

### Resource Filtering (GET /resources)
| Parameter | Type | Description |
|-----------|------|-------------|
| type | string | Filter by resource type |
| status | string | Filter by status |
| organization | string | Filter by organization (partial match) |
| limit | integer | Max results (1-500, default 100) |
| offset | integer | Pagination offset |

### Nearby Resource Search

#### GET /resources/nearby
| Parameter | Type | Description |
|-----------|------|-------------|
| latitude | float | Search center latitude (-90 to 90) |
| longitude | float | Search center longitude (-180 to 180) |
| radius_meters | float | Search radius (default 2000, max 10000) |
| type | string | Filter by resource type |
| status | string | Filter by status |
| limit | integer | Max results (1-200, default 100) |
| offset | integer | Pagination offset |

#### GET /resources/nearby/counts
Returns counts of nearby resources grouped by type.

#### GET /resources/{id}/geojson
Returns a single resource as GeoJSON Feature.

### Incident-Specific Resource Endpoints

#### GET /incidents/{incident_id}/nearby-resources
| Parameter | Type | Description |
|-----------|------|-------------|
| radius_meters | float | Search radius (default 1000, max 10000) |
| type | string | Filter by resource type |
| status | string | Filter by status |
| limit | integer | Max results (1-200) |
| offset | integer | Pagination offset |

#### GET /incidents/{incident_id}/nearby-resources/{type}
Get nearby resources of a specific type for an incident.

#### GET /incidents/{incident_id}/resource-counts
Get counts of nearby resources grouped by type.

#### GET /incidents/{incident_id}/map-data
Returns GeoJSON FeatureCollection for map visualization:
- Incident point
- Analysis area polygon
- Nearby infrastructure points (categorized by type)

---

## Frontend Features

### Resources Tab
- **Resource List**: Paginated, filterable, searchable list
- **Filters**: Type, Status, Organization
- **Resource Cards**: Show name, type, status, location, capacity, organization
- **Resource Detail View**: Click any resource to see full details
- **Status Management**: Buttons to change status (Available, Deployed, Maintenance, Unavailable)
- **Add Resource Form**: Complete form with validation

### Incident Resource View
- **Incident Detail**: Shows nearby resources in a table
- **Filters**: Type, Status, Radius
- **Distance Display**: Shows distance in meters
- **Quick Filters**: Tabs for Hospitals, Shelters, Fire Stations, etc.

### Map Integration
- **Map Tab**: Shows incident location, analysis area, and nearby resources
- **Layer Controls**: Toggle visibility of each resource type
- **Resource Markers**: Color-coded by type, with icons
- **Resource Popups**: Click for details

---

## Data Loader

### Sample Data Files
- `data/resources.json` - 15 synthetic emergency resources (Bengaluru area)
- `data/load_resources.py` - Async loader script

### Running the Loader
```bash
cd resq-ai/data
python load_resources.py
```

---

## Configuration

### Environment Variables (`.env`)
```bash
# Resource Configuration (Phase 7)
DEFAULT_RESOURCE_SEARCH_RADIUS_METERS=2000
MAX_RESOURCE_SEARCH_RADIUS_METERS=10000
```

### Pydantic Settings (config.py)
```python
DEFAULT_RESOURCE_SEARCH_RADIUS_METERS: float = Field(default=2000.0, alias="DEFAULT_RESOURCE_SEARCH_RADIUS_METERS")
MAX_RESOURCE_SEARCH_RADIUS_METERS: float = Field(default=10000.0, alias="MAX_RESOURCE_SEARCH_RADIUS_METERS")
```

---

## Testing

### Unit Tests
```bash
cd resq-ai/backend
pytest tests/test_resource.py tests/test_resource_api.py -v
```

### Test Coverage
- Resource CRUD operations
- Geospatial queries (distance, radius)
- Validation (coordinates, capacity, types)
- Incident-resource integration
- Geospatial service methods
- API endpoint validation

### Test Types
- **Unit Tests**: Mocked database, no external dependencies
- **Integration Tests**: Full API flow with database

---

## Map Integration

### MapView Component
- **MapLibre GL JS** with OpenStreetMap tiles
- **Layer Controls**: Toggle resource types on/off
- **Resource Markers**: Color-coded by type with icons
- **Incident Point**: Red circle marker
- **Analysis Area**: Blue polygon overlay
- **Resource Popups**: Click for details

### Resource Icons & Colors
| Type | Icon | Color |
|------|------|-------|
| hospital | 🏥 | #e53935 |
| shelter | 🏠 | #43a047 |
| fire_station | 🚒 | #fb8c00 |
| police_unit | 👮 | #1e88e5 |
| school | 🏫 | #8e24aa |
| bridge | 🌉 | #546e7a |
| road | 🛣️ | #78909c |
| emergency_center | 🚨 | #00acc1 |
| power_station | ⚡ | #fdd835 |
| water_facility | 💧 | #29b6f6 |

---

## Database Migration

### Creating the Migration
```bash
cd resq-ai/backend
alembic revision --autogenerate -m "Add resources table"
alembic upgrade head
```

### PostGIS Requirements
- PostgreSQL 15+ with PostGIS 3.4+
- Enable extension: `CREATE EXTENSION postgis;`
- Spatial indexes on `location` column

---

## Limitations (Prototype)

1. **Synthetic Data**: Resources are synthetic, not real-world
2. **Static Availability**: No real-time tracking
3. **No Travel Time**: Geographic distance ≠ travel time
4. **No Dispatch Logic**: Phase 8 will add optimization
5. **Synthetic Population**: Uses sample population zones
6. **No Real Weather**: Environmental conditions are synthetic

---

## Next Steps (Phase 8)

- Resource optimization & dispatch
- Travel time calculation (OSRM/GraphHopper integration)
- Multi-resource assignment
- Real-time availability updates
- AI-assisted dispatch recommendations
- Resource scheduling & rotation

---

## Security Considerations

- Input validation on all endpoints
- Coordinate bounds checking
- Capacity/load constraints enforced
- SQL injection prevention via SQLAlchemy ORM
- CORS configured for frontend origin only
- No authentication yet (Phase 7 scope)