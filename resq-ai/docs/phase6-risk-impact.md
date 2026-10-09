# Phase 6: Dynamic Risk & Impact Assessment — Architecture & Design

## Overview

Phase 6 implements a transparent, evidence-based risk and impact assessment engine for disaster incidents. It combines information from Phase 2 (AI analysis), Phase 3 (incident clustering), Phase 4 (evidence investigation), and Phase 5 (geospatial intelligence) to produce a structured risk assessment with explainable components.

**Core Principle**: Decision-support system, not autonomous decision-maker. Every risk score is traceable to specific evidence and factors.

---

## Architecture

```
Incident (Phase 3)
    ↓
Phase 2 AI Analysis
    ↓
Phase 4 Evidence Investigation
    ↓
Phase 5 Geographic Intelligence
    ↓
Risk & Impact Engine
    ↓
Risk Assessment + Impact Assessment
    ↓
Future Resource Optimization (Phase 7+)
```

---

## Risk Model

### Component Weights (Configurable via `.env`)

| Component | Weight | Description |
|-----------|--------|-------------|
| Severity | 0.25 | Disaster type, severity indicators, damage, people affected |
| Evidence | 0.20 | Investigation confidence, supporting/contradicting evidence, source diversity |
| Population | 0.25 | Population potentially exposed, vulnerability factors |
| Infrastructure | 0.15 | Critical infrastructure exposure, weighted by type |
| Environment | 0.10 | Rainfall, wind, water level, temperature |
| Accessibility | 0.05 | Road/bridge status, emergency access |

**Sum**: 1.0 (enforced by design)

### Risk Level Thresholds (0-100 scale)

| Level | Score Range | Description |
|-------|-------------|-------------|
| Low | 0-19 | Minimal risk, routine monitoring |
| Moderate | 20-39 | Some risk factors present |
| Elevated | 40-59 | Significant risk factors |
| High | 60-79 | Multiple serious risk factors |
| Critical | 80-100 | Maximum risk, immediate attention |

---

## Component Calculations

### 1. Severity Component (0-100)
Based on Phase 2 AI analysis:
- Disaster type confidence × 40
- Severity indicators count × 5 (max 30)
- Damage observed count × 8 (max 25)
- People affected reported: +15
- Infrastructure damage count × 5 (max 15)

### 2. Evidence Component (0-100)
Based on Phase 4 investigation:
- Evidence confidence × 40
- Supporting evidence count × 4 (max 20)
- Contradicting evidence × -5 (max -20)
- Source diversity × 15
- Multimodal consistency × 15
- Geographic consistency × 10

### 3. Population Component (0-100)
Uses PostGIS to find population zones within incident radius:
- Total population in radius
- Distance-weighted exposure (closer = higher)
- Vulnerability factor per zone (0-1)
- Score = min(weighted_exposure / 200, 100)

### 4. Infrastructure Component (0-100)
PostGIS query for infrastructure within radius:
- Weighted by type criticality (configurable)
- Distance decay factor
- Hospitals=10, Shelters=8, Emergency Centers=8, Fire Stations=6, Bridges=7, Power/Water=6, Police=5, Schools=4, Roads=3
- Score = min(total_weight × 2, 100)

### 5. Environment Component (0-100)
From `environmental_conditions` table:
- Rainfall: >50mm/h=30, >20=20, >10=10, >5=5
- Wind: >80km/h=20, >50=15, >30=10, >15=5
- Water level: >2m=30, >1m=20, >0.5m=10
- Temperature extremes (>40°C or <0°C): +10

### 6. Accessibility Component (0-100, inverted for risk)
Road/bridge status from infrastructure:
- Open roads/bridges increase accessibility
- Blocked/partially blocked decrease accessibility
- Score = open_ratio × 100
- For risk: inverted (100 - accessibility_score)

---

## Risk Score Calculation

```
risk_score = Σ(component_score × weight)

Where:
- accessibility_risk = 100 - accessibility_score (inverted)
- All weights sum to 1.0
- Result clamped to [0, 100]
```

---

## Impact Assessment

Separate from risk score. Quantifies what could be affected:

| Metric | Description |
|--------|-------------|
| population_potentially_exposed | Total population in incident radius |
| population_zones_count | Number of population zones affected |
| population_weighted_exposure | Distance-weighted vulnerable population |
| infrastructure_potentially_exposed | Total infrastructure in radius |
| hospitals/shelters/fire_stations/..._count | By type |
| roads_potentially_affected | Blocked + partially blocked roads |
| bridges_potentially_affected | Blocked bridges |
| accessibility_status | open / partially_blocked / blocked / unknown |

**Key distinction**: Risk = likelihood × consequence; Impact = what is in harm's way.

---

## Database Schema

### `population_zones`
- `id` (UUID PK)
- `name`, `population`, `latitude`, `longitude`
- `location` (PostGIS POINT, SRID 4326)
- `geometry` (PostGIS POLYGON, optional)
- `vulnerability_factor` (0-1, default 0.5)
- `metadata` (JSONB)

### `environmental_conditions`
- `id` (UUID PK)
- `incident_id` (FK → incidents, CASCADE)
- `timestamp`, `temperature`, `rainfall`, `wind_speed`
- `humidity`, `water_level`, `visibility`
- `weather_description`, `metadata` (JSONB)

### `risk_assessments`
- `id` (UUID PK)
- `incident_id` (FK → incidents, CASCADE)
- `risk_score` (0-100), `risk_level` (ENUM)
- Component scores (6 fields, 0-100 each)
- Component details (JSONB)
- `explanation`, `model_name`, `assessed_at`

### `impact_assessments`
- `id` (UUID PK)
- `incident_id` (FK → incidents, CASCADE)
- Population: `potentially_exposed`, `zones_count`, `weighted_exposure`
- Infrastructure: `potentially_exposed`, counts by type (10 fields)
- Accessibility: `status`, `details` (JSONB)
- `explanation`, `assessed_at`

### `risk_assessment_history`
- `id` (UUID PK)
- `incident_id` (FK → incidents, CASCADE)
- `risk_score`, `risk_level`, all 6 components
- `explanation`, `trigger` (manual/auto/scheduled/environmental_change/recalculate)
- `assessed_at`

---

## API Endpoints

### Risk Assessment
```
POST   /api/v1/incidents/{incident_id}/risk-assessment      # Run assessment
GET    /api/v1/incidents/{incident_id}/risk-assessment      # Get latest
POST   /api/v1/incidents/{incident_id}/risk-assessment/recalculate  # Recalculate
GET    /api/v1/incidents/{incident_id}/risk-history         # History (with limit)
```

### Impact Assessment
```
GET    /api/v1/incidents/{incident_id}/impact               # Get latest
POST   /api/v1/incidents/{incident_id}/impact/recalculate   # Recalculate
```

---

## Dynamic Risk

Risk is recalculated when:
- New events added to incident
- New AI analysis available
- Evidence investigation updated
- Environmental conditions change
- Manual recalculation requested

History table stores full assessment trail for trend analysis.

---

## Frontend

### Risk & Impact Tab
- **Incident Summary**: Type, events, status, confidence, location, timestamps
- **Actions**: Run Assessment, Recalculate, View Impact, View History
- **Risk Result**: Score circle, level badge, component bars, explanation
- **Component Details**: Expandable JSON for each component
- **Impact Assessment**: Population, infrastructure counts, accessibility
- **Risk History**: Timeline with score, level, components, trigger

---

## Configuration (`.env`)

```bash
# Risk weights (must sum to 1.0)
RISK_WEIGHT_SEVERITY=0.25
RISK_WEIGHT_EVIDENCE=0.20
RISK_WEIGHT_POPULATION=0.25
RISK_WEIGHT_INFRASTRUCTURE=0.15
RISK_WEIGHT_ENVIRONMENT=0.10
RISK_WEIGHT_ACCESSIBILITY=0.05

# Risk thresholds
RISK_LEVEL_LOW_MAX=19
RISK_LEVEL_MODERATE_MAX=39
RISK_LEVEL_ELEVATED_MAX=59
RISK_LEVEL_HIGH_MAX=79

# Infrastructure criticality weights
INFRA_WEIGHT_HOSPITAL=10.0
INFRA_WEIGHT_SHELTER=8.0
INFRA_WEIGHT_FIRE_STATION=6.0
INFRA_WEIGHT_POLICE_STATION=5.0
INFRA_WEIGHT_BRIDGE=7.0
INFRA_WEIGHT_ROAD=3.0
INFRA_WEIGHT_EMERGENCY_CENTER=8.0
INFRA_WEIGHT_POWER_STATION=6.0
INFRA_WEIGHT_WATER_FACILITY=6.0
INFRA_WEIGHT_SCHOOL=4.0
```

---

## Test Scenarios

### Scenario A — Low Impact
- Small population exposure, few infrastructure, good accessibility
- Expected: Low/Moderate risk

### Scenario B — High Population Exposure
- Large population, several critical infrastructure
- Expected: High risk

### Scenario C — Poor Accessibility
- Multiple roads/bridges blocked
- Expected: Elevated/High risk

### Scenario D — Changing Conditions
- Environmental conditions worsen
- Recalculation increases risk
- History shows trend

---

## Limitations

1. **Prototype weights**: All weights/thresholds are configurable prototypes, not validated standards
2. **Synthetic population**: Uses sample zones, not real census data
3. **No real-time weather**: Environmental data is synthetic/sample
4. **Static radius**: Analysis radius is fixed (configurable), not dynamic
5. **No causal modeling**: Correlation ≠ causation
6. **Evidence ≠ Truth**: High evidence confidence ≠ actual disaster severity
7. **Population aggregates**: No individual-level data, only zone aggregates

---

## Future Enhancements (Phase 7+)

- Real census data integration
- Live weather API integration
- Dynamic radius based on disaster type
- Resource optimization integration
- Evacuation route planning
- Monte Carlo simulation for uncertainty
- ML-based weight optimization