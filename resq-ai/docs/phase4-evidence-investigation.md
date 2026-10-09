# Phase 4: AI Evidence Investigation — Architecture & Design

## Overview

Phase 4 implements an evidence-based investigation system for disaster incidents. Unlike traditional misinformation classifiers that output binary "real/fake" labels, this system produces a nuanced, traceable evidence assessment that explains **why** the system believes an incident represents a real or potentially real disaster.

**Core Principle**: Evidence investigation, not truth classification. The system distinguishes between observed facts, AI interpretations, and uncertainty.

---

## Architecture

```
Incident (Phase 3)
        ↓
┌─────────────────────────────────────────────────────────────┐
│                    Evidence Collector                       │
│  • Text reports (Phase 1)                                   │
│  • AI analysis: text, image, video (Phase 2)                │
│  • Clustering relationships (Phase 3)                       │
└─────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────┐
│                  Evidence Analyzers                         │
│  • Text evidence (directness, uncertainty, specificity)    │
│  • Image evidence (visual confirmation, confidence)        │
│  • Video evidence (temporal consistency across frames)     │
│  • Geographic consistency (distance from incident center)  │
│  • Temporal consistency (event time clustering)            │
│  • Multimodal consistency (cross-modal agreement)          │
│  • Source diversity (independent source types)             │
└─────────────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────────────┐
│                    AI Evidence Investigator                 │
│  • Receives structured evidence items                       │
│  • Produces investigation report with assessment           │
│  • Does NOT invent evidence                                 │
└─────────────────────────────────────────────────────────────┘
        ↓
IncidentInvestigation + Evidence tables
```

---

## Evidence Model

### Evidence Types (`EvidenceType`)

| Type | Description | Source |
|------|-------------|--------|
| `text` | Original text reports from events | Phase 1 ingestion |
| `image` | AI image analysis results | Phase 2 |
| `video` | AI video analysis results | Phase 2 |
| `geographic` | Distance consistency from incident center | Phase 3 |
| `temporal` | Time clustering of events | Phase 3 |
| `multimodal` | Cross-modal agreement on disaster type | Phase 2+3 |
| `source_diversity` | Number of independent source types | Phase 1 |
| `consistency` | General consistency measures | Derived |

### Evidence Roles (`EvidenceRole`)

| Role | Meaning | Example |
|------|---------|---------|
| `supporting` | Strengthens belief in incident | "Water covering road" + flood image |
| `contradicting` | Weakens belief in incident | "Road is clear" during flood incident |
| `neutral` | Neither supports nor contradicts | "Weather is cloudy" |
| `uncertain` | Report contains hedging/uncertainty | "Someone said there might be flooding" |

### Evidence Quality (0-1)

Calculated per evidence item based on:
- **Text**: Length, specificity, AI confidence, uncertainty language
- **Image/Video**: AI confidence, damage observations, severity indicators
- **Geographic**: Distance from incident center (inverse relationship)
- **Temporal**: Event time clustering tightness
- **Multimodal**: Cross-modal disaster type agreement
- **Source Diversity**: Number of independent source types

---

## Evidence Collection (`evidence_collector.py`)

For each incident, the collector gathers:

### From Phase 1 Events
- Original text content
- Source type (social_media, news, satellite, etc.)
- Timestamp and coordinates
- Location name

### From Phase 2 AI Analysis
- Text analysis: disaster type, severity, damage, summary
- Image analysis: visual observations, confidence
- Video analysis: frame-by-frame observations

### From Phase 3 Incident Relationships
- Incident-event assignment
- Relationship score components (semantic, geographic, temporal)
- Incident centroid

### Derived Evidence
- **Text**: Role determined by language analysis (uncertainty keywords, contradiction keywords)
- **Image/Video**: Role from AI confidence thresholds
- **Geographic**: Average distance from incident centroid
- **Temporal**: Event time spread (duration, event count)
- **Multimodal**: Disaster type agreement across modalities
- **Source Diversity**: Unique source type count

---

## Investigation Process

### 1. Evidence Extraction
```python
# For each event in incident:
extract_text_evidence(event)      # → Evidence items
extract_image_evidence(event)     # → Evidence items
extract_video_evidence(event)     # → Evidence items

# For incident as whole:
extract_geographic_evidence(collection)
extract_temporal_evidence(collection)
extract_multimodal_consistency(collection)
extract_source_diversity(collection)
```

### 2. Evidence Storage
All evidence items stored in `evidence` table with:
- Link to incident and event
- Type, role, description, quality, confidence
- Metadata for traceability

### 3. AI Investigation
Structured prompt sent to Qwen2.5-VL with:
- Incident summary (type, title, event count, location)
- All evidence items with type, role, quality, confidence
- Component scores (source diversity, geographic, temporal, multimodal)
- Output: structured JSON with assessment, explanation, limitations

### 4. Assessment Values
| Assessment | Meaning | Typical Conditions |
|------------|---------|-------------------|
| `strongly_supported` | High confidence, multiple sources, multimodal agreement | 4+ supporting, diverse sources, high consistency |
| `moderately_supported` | Good evidence, some gaps | 2-3 supporting, moderate consistency |
| `weakly_supported` | Limited but positive evidence | 1-2 supporting, low diversity/consistency |
| `conflicting` | Significant contradictory evidence | Multiple contradicting items |
| `insufficient_evidence` | Too few items to conclude | 0-1 evidence items |
| `inconclusive` | Evidence exists but ambiguous | Mixed signals, no clear direction |

---

## Database Schema

### `evidence` table
```sql
CREATE TABLE evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID REFERENCES incidents(id) ON DELETE CASCADE,
    event_id UUID REFERENCES events(id) ON DELETE SET NULL,
    evidence_type VARCHAR(50) NOT NULL,  -- Enum: text, image, video, geographic, temporal, multimodal, consistency, source_diversity
    evidence_role VARCHAR(50) NOT NULL,  -- Enum: supporting, contradicting, neutral, uncertain
    description TEXT NOT NULL,
    evidence_quality FLOAT,  -- 0-1
    confidence FLOAT,        -- 0-1
    source VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT now()
);
```

### `incident_investigations` table
```sql
CREATE TABLE incident_investigations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID REFERENCES incidents(id) ON DELETE CASCADE,
    supporting_evidence_count INTEGER DEFAULT 0,
    contradicting_evidence_count INTEGER DEFAULT 0,
    neutral_evidence_count INTEGER DEFAULT 0,
    uncertain_evidence_count INTEGER DEFAULT 0,
    evidence_confidence FLOAT,  -- 0-1 overall confidence
    assessment VARCHAR(50) NOT NULL,  -- Enum: strongly_supported, moderately_supported, weakly_supported, conflicting, insufficient_evidence, inconclusive
    explanation TEXT,
    limitations TEXT,
    source_diversity FLOAT,
    geographic_consistency FLOAT,
    temporal_consistency FLOAT,
    multimodal_consistency FLOAT,
    model_name VARCHAR(200),
    investigated_at TIMESTAMP DEFAULT now(),
    created_at TIMESTAMP DEFAULT now()
);
```

---

## API Endpoints

### POST `/api/v1/incidents/{incident_id}/investigate`
Run evidence investigation for an incident.

**Request:**
```json
{
  "force_rerun": false
}
```

**Response (201):**
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
  "explanation": "Supporting evidence (5 items) includes: Text report: Heavy flooding...; Image analysis: Street-level view showing flood water...; Geographic consistency: 3 events, avg distance 250m...",
  "limitations": "Limited source diversity; all reports may originate from similar channels. Standard evidence limitations apply.",
  "source_diversity": 0.6,
  "geographic_consistency": 0.9,
  "temporal_consistency": 0.85,
  "multimodal_consistency": 0.7,
  "model_name": "Qwen/Qwen2.5-VL-3B-Instruct",
  "investigated_at": "2026-09-21T12:00:00"
}
```

### GET `/api/v1/incidents/{incident_id}/investigation`
Retrieve stored investigation (no auto-run).

### GET `/api/v1/incidents/{incident_id}/investigation-summary`
Detailed summary with categorized evidence.

**Response:**
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
  "explanation": "Supporting evidence (5 items) includes...",
  "limitations": "Limited source diversity...",
  "model_name": "Qwen/Qwen2.5-VL-3B-Instruct",
  "investigated_at": "2026-09-21T12:00:00"
}
```

### GET `/api/v1/incidents/{incident_id}/evidence`
Retrieve raw evidence items with filters.

**Query params:**
- `evidence_type`: Filter by type
- `evidence_role`: Filter by role
- `limit`, `offset`: Pagination

---

## Frontend

### Route: `/incidents` → Incident list
Click incident → Opens investigation view

### Investigation View Shows:
1. **Incident Summary**: Type, title, event count, status, confidence, location, timestamps
2. **Investigation Actions**: "Investigate Incident" / "View Stored Investigation"
3. **Metrics Dashboard**: Evidence confidence, source diversity, geographic, temporal, multimodal consistency (with progress bars)
4. **Explanation**: Natural language assessment
5. **Limitations**: Documented limitations
6. **Categorized Evidence**:
   - Supporting (green border)
   - Contradicting (red border)
   - Uncertain (orange border)
   - Neutral (gray border)
7. **Raw JSON** for debugging

---

## Test Scenarios

### Scenario A — Strongly Consistent Evidence
- 4 events: 2 text + 1 image + 1 video, all flood
- 3 source types
- Tight geographic (200m avg) and temporal (30 min) clustering
- **Expected**: `strongly_supported`, high confidence

### Scenario B — Limited Evidence
- 1 event: uncertain text report ("might be flooding")
- No image/video
- Single source
- **Expected**: `insufficient_evidence` or `weakly_supported`

### Scenario C — Contradictory Evidence
- 2 events: flood text + image
- 1 event: "road is clear" text (contradicting)
- **Expected**: `conflicting` or `weakly_supported`

### Scenario D — Geographic Inconsistency
- 2 flood events: 50km apart
- Same time window
- **Expected**: Low geographic consistency, affects overall score

---

## Limitations (Documented)

1. **No External Verification**: Only analyzes internally collected evidence. No web/news fact-checking.
2. **Source Independence Assumed**: Different source types ≠ truly independent sources. Same event may appear on multiple platforms.
3. **AI Interpretation Uncertainty**: Phase 2 AI analyses have their own confidence scores; these propagate through.
4. **No Temporal Causality**: Temporal clustering ≠ causal relationship. Coincident events may be unrelated.
5. **Geographic Proximity ≠ Same Event**: Nearby events may be separate incidents.
6. **Language Bias**: Uncertainty detection based on English keywords; may not generalize.
7. **No Credibility Assessment**: Does not assess source credibility (e.g., verified accounts vs anonymous).
8. **Image/Video Provenance**: Does not verify when/where media was captured unless metadata available.

---

## Configuration (`.env`)

Inherits from Phase 2/3:
```bash
# AI Model (shared)
AI_MODEL_NAME=Qwen/Qwen2.5-VL-3B-Instruct

# Clustering (Phase 3)
SEMANTIC_SIMILARITY_THRESHOLD=0.75
MAX_DISTANCE_METERS=2000
MAX_TIME_DIFFERENCE_MINUTES=120

# Investigation weights (could be added if needed)
# EVIDENCE_TEXT_WEIGHT=0.3
# EVIDENCE_IMAGE_WEIGHT=0.25
# EVIDENCE_VIDEO_WEIGHT=0.2
# EVIDENCE_GEOGRAPHIC_WEIGHT=0.15
# EVIDENCE_TEMPORAL_WEIGHT=0.1