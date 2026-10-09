# Phase 2: Multimodal AI Analysis — Architecture & Design

## Overview

Phase 2 implements the multimodal AI analysis layer for RESQ-AI. It uses open-source vision-language models (Qwen2.5-VL family) to analyze disaster-related text, images, and videos, producing structured `DisasterAnalysis` output that subsequent phases can consume.

**Key Principle**: Pure analysis — no clustering, risk scoring, or decision-making. Those belong to Phase 3+.

---

## AI Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer                                │
│  POST /events/{id}/analyze  →  GET /events/{id}/analysis       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   EventAnalyzer Service                         │
│  • Coordinates text/image/video analysis                       │
│  • Merges multimodal results                                   │
│  • Stores in event_ai_analysis table                           │
└─────────────────────────────────────────────────────────────────┘
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Text Analyzer  │  │  Image Analyzer │  │  Video Analyzer │
│  (analyze_text) │  │ (analyze_image) │  │ (analyze_video) │
└─────────────────┘  └─────────────────┘  └─────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   BaseMultimodalModel                           │
│  Abstract interface: load(), analyze_text(), analyze_image(),  │
│  analyze_frames(), unload(), is_loaded(), model_name           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   QwenVLModel (Implementation)                 │
│  • HuggingFace AutoModelForVision2Seq + AutoProcessor          │
│  • Device auto-detection (CUDA/MPS/CPU)                        │
│  • Configurable dtype (float16/bfloat16/float32)               │
│  • Memory management (offload, max_memory)                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Selected Model: Qwen2.5-VL

### Why Qwen?

| Factor | Qwen2.5-VL | Alternatives Considered |
|--------|------------|------------------------|
| **Open License** | Apache 2.0 ✓ | LLaVA (varies), Idefics (Apache 2.0) |
| **Vision-Language** | Native multimodal ✓ | Most require separate models |
| **Model Sizes** | 2B, 3B, 7B, 72B ✓ | Limited size options |
| **Performance** | Strong on OCR, reasoning | Comparable |
| **Hardware Flexibility** | Runs on 4-14GB VRAM | Some need >24GB |
| **Active Maintenance** | Alibaba Qwen team | Varies |

### Model Size Selection Guide

| Model | VRAM (bf16) | RAM (CPU) | Speed | Accuracy | Use Case |
|-------|-------------|-----------|-------|----------|----------|
| Qwen2-VL-2B | ~4 GB | ~8 GB | Fastest | Good | Edge/CPU |
| **Qwen2.5-VL-3B** | **~6 GB** | **~12 GB** | **Fast** | **Very Good** | **Default** |
| Qwen2.5-VL-7B | ~14 GB | ~28 GB | Medium | Excellent | GPU Server |
| Qwen2.5-VL-72B | ~140 GB | N/A | Slow | Best | H100/A100 |

**Default**: `Qwen/Qwen2.5-VL-3B-Instruct` — best balance for development.

### Configuration

All model settings in `.env`:

```bash
# Model selection
AI_MODEL_NAME=Qwen/Qwen2.5-VL-3B-Instruct
AI_MODEL_REVISION=main

# Hardware
AI_DEVICE=auto          # auto, cuda, cpu, mps
AI_DTYPE=auto           # auto, float16, bfloat16, float32
AI_MAX_MEMORY=8GiB      # Per-GPU limit (optional)
AI_OFFLOAD_FOLDER=./offload  # CPU offload (optional)

# Inference
AI_MAX_NEW_TOKENS=1024
AI_TEMPERATURE=0.1
AI_TOP_P=0.9
AI_DO_SAMPLE=false

# Video
VIDEO_FRAME_INTERVAL=5   # 1 frame per 5 seconds
VIDEO_MAX_FRAMES=20

# Images
MAX_IMAGE_SIZE=1024      # Resize larger images
```

---

## Common Output Schema: DisasterAnalysis

All modalities produce the same structured output:

```python
class DisasterAnalysis(BaseModel):
    disaster_type: Optional[DisasterType]      # flood, wildfire, earthquake, etc.
    disaster_type_confidence: Optional[float]  # 0.0 - 1.0
    severity_indicators: List[str]             # ["water rising rapidly", "evacuation underway"]
    location_mentions: List[str]               # ["city center", "highway 101"]
    damage_observed: List[str]                 # ["vehicles submerged", "collapsed roof"]
    people_affected: Optional[str]             # "residents requesting rescue" or null
    vehicles_observed: List[str]               # ["stuck cars", "fire trucks"]
    infrastructure_damage: List[str]           # ["road flooded", "power lines down"]
    environmental_conditions: List[str]        # ["heavy rain", "night", "smoke"]
    summary: str                               # 2-3 sentence summary
    evidence_description: str                  # What was analyzed
```

**Key Rules:**
- `null` for unavailable strings, `[]` for unavailable arrays
- Never hallucinate numbers ("500 people" → `null` unless explicitly stated)
- Distinguish OBSERVED from ASSUMED in evidence_description

---

## Text Analysis

### Function: `analyze_text(text: str) -> DisasterAnalysis`

**Input**: Disaster-related text (social media, news, reports)

**Process**:
1. Load prompt template from `ai/prompts/text_analysis.txt`
2. Format with input text
3. Send to model via `model.analyze_text()`
4. Parse JSON response into `DisasterAnalysis`

**Prompt Design** (`text_analysis.txt`):
- Explicit JSON schema with field descriptions
- Rules: no hallucination, use null/empty for unavailable
- Disaster type enum with 15 categories
- Confidence scoring instruction

**Example Input:**
```
"Heavy flooding has covered the main road near the city center. 
Water levels are rising rapidly and several vehicles are stuck. 
Residents are requesting immediate rescue assistance."
```

**Example Output:**
```json
{
  "disaster_type": "flood",
  "disaster_type_confidence": 0.92,
  "severity_indicators": ["water rising rapidly", "vehicles stuck", "rescue requested"],
  "location_mentions": ["city center", "main road"],
  "damage_observed": ["road flooded", "vehicles submerged"],
  "people_affected": "residents requesting rescue",
  "vehicles_observed": ["stuck vehicles"],
  "infrastructure_damage": ["main road flooded"],
  "environmental_conditions": ["heavy rain"],
  "summary": "Heavy flooding on main road near city center with vehicles stuck and rescue requested.",
  "evidence_description": "Text analysis: Social media post describing flooding"
}
```

---

## Image Analysis

### Function: `analyze_image(image_path: str) -> DisasterAnalysis`

**Input**: Path to image file (JPG, PNG, WebP, BMP)

**Process**:
1. Validate path exists, is file, supported format
2. Load image with PIL, resize if > MAX_IMAGE_SIZE (default 1024px)
3. Load prompt from `ai/prompts/image_analysis.txt`
4. Send image + prompt to model via `model.analyze_image()`
5. Parse JSON response

**Prompt Design** (`image_analysis.txt`):
- Emphasizes VISUALLY OBSERVABLE only
- Distinguishes OBSERVED vs ASSUMED
- Same JSON schema as text

**Example Analysis:**
- Input: Street photo with flood water covering road, cars partially submerged
- Output: `disaster_type="flood"`, confidence 0.88, severity includes "water covering road", "water above curb level"

---

## Video Analysis

### Function: `analyze_video(video_path: str) -> DisasterAnalysis`

**Input**: Path to video file (MP4, AVI, MOV, MKV, WebM)

**Process**:
1. Validate path and format
2. Open with OpenCV, get FPS, frame count, duration
3. Calculate frame interval: `fps * VIDEO_FRAME_INTERVAL` (default 5 seconds)
4. Extract frames at intervals, up to `VIDEO_MAX_FRAMES` (default 20)
5. Save frames to temp directory
6. Send all frames + prompt to model via `model.analyze_frames()`
7. Parse JSON response
8. Clean up temp frames

**Prompt Design** (`video_analysis.txt`):
- Receives frame analyses as context
- Analyzes temporal progression
- Notes changes between frames (rising water, spreading fire)

**Frame Sampling Example:**
```
Video: 60 seconds, 30 fps = 1800 frames
Interval: 5 seconds → sample every 150 frames
Frames: 0, 150, 300, 450, 600, 750, 900, 1050, 1200, 1350, 1500, 1650
Total: 12 frames analyzed (under 20 max)
```

---

## Multimodal Fusion

### Function: `analyze_multimodal(text, image_path, video_path)`

**Logic:**
```python
def analyze_multimodal(text, image_path, video_path):
    analyses = []
    
    if text: analyses.append(analyze_text(text))
    if image_path: analyses.append(analyze_image(image_path))
    if video_path: analyses.append(analyze_video(video_path))
    
    if not analyses:
        return empty_analysis()
    
    # Merge: combine unique observations, take max confidence
    combined = analyses[0]
    for a in analyses[1:]:
        combined = combined.merge_with(a)
    
    combined.evidence_description = f"Multimodal ({modalities}): {combined.evidence_description}"
    return combined
```

**Merge Strategy (`DisasterAnalysis.merge_with()`):**
- `disaster_type`: First non-null
- `confidence`: Maximum
- Arrays: Union (deduplicated)
- Strings: First non-null
- `evidence_description`: Concatenated with separator

---

## Database Integration

### Table: `event_ai_analysis`

```sql
CREATE TABLE event_ai_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES events(id) ON DELETE CASCADE,
    modality VARCHAR(50) NOT NULL,
    disaster_type VARCHAR(50),
    disaster_type_confidence JSONB,
    severity_indicators JSONB DEFAULT '[]',
    location_mentions JSONB DEFAULT '[]',
    damage_observed JSONB DEFAULT '[]',
    people_affected TEXT,
    vehicles_observed JSONB DEFAULT '[]',
    infrastructure_damage JSONB DEFAULT '[]',
    environmental_conditions JSONB DEFAULT '[]',
    summary TEXT,
    evidence_description TEXT,
    model_name VARCHAR(200) NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX ix_event_ai_analysis_event_created ON event_ai_analysis(event_id, created_at);
```

**Design Decisions:**
- Separate table preserves raw event data
- JSONB for flexible array/object storage
- Multiple analyses per event supported (versioning)
- `model_name` tracks which model produced analysis

---

## API Endpoints

### POST `/api/v1/events/{event_id}/analyze`

**Request:**
```json
{
  "text": "optional override",
  "image_path": "/optional/override/path.jpg",
  "video_path": "/optional/override/path.mp4"
}
```

**Flow:**
1. Fetch event from DB
2. Determine modalities (event fields + request overrides)
3. Validate at least one modality available
4. Run `EventAnalyzer.analyze_event()`
5. Store `EventAIAnalysis` record
6. Return structured response

**Errors:**
- `404`: Event not found
- `422`: No analyzable content

### GET `/api/v1/events/{event_id}/analysis`

**Returns:** Latest `EventAIAnalysis` for event

**Behavior:** Does NOT trigger analysis. Returns 404 if none exists.

---

## Testing Strategy

### Unit Tests (`tests/test_ai_analysis.py`)
- Mock `model_manager` to return predefined `DisasterAnalysis`
- Test all analyzer functions with mocked responses
- Test multimodal merge logic
- Test validation (empty input, bad paths)
- **No model loaded** — runs in <1 second

### Integration Tests (`tests/test_analysis_api.py`)
- Use in-memory SQLite
- Mock `EventAnalyzer.analyze_event` to return test data
- Test full API flow: create event → analyze → retrieve
- Test persistence in database
- **Optional**: Set `AI_INTEGRATION_TESTS=1` to use real model (slow)

### Running Tests
```bash
# Fast unit tests only
pytest tests/test_events.py tests/test_ai_analysis.py -v

# All tests (includes API integration)
pytest tests/ -v

# With real model (requires GPU, slow)
AI_INTEGRATION_TESTS=1 pytest tests/test_analysis_api.py -v
```

---

## Error Handling

| Error Type | Handling |
|------------|----------|
| Model not loaded | Auto-load on first request |
| OOM / GPU memory | Configurable `AI_MAX_MEMORY`, CPU offload |
| Invalid image | Validate format/size before sending to model |
| Invalid video | Validate format, OpenCV error handling |
| Corrupted media | Try/except with clean error response |
| Timeout | `AI_INFERENCE_TIMEOUT` (default 300s) |
| Malformed JSON | Fallback to raw response in evidence_description |
| Model unavailable | 503 with clear message |

**API Errors** never expose stack traces. Technical details logged server-side.

---

## Performance Optimization

| Technique | Implementation |
|-----------|----------------|
| **Model Reuse** | Singleton `ModelManager` keeps model in memory |
| **Lazy Loading** | Model loads on first `/analyze` request |
| **Video Sampling** | Configurable frame interval (default 5s) |
| **Image Resize** | Auto-resize >1024px before sending to model |
| **CPU Fallback** | Auto-detects device, supports CPU inference |
| **Memory Management** | `torch.cuda.empty_cache()` on unload |

---

## Hardware Requirements

| Configuration | Minimum | Recommended |
|---------------|---------|-------------|
| **GPU VRAM** | 4 GB (2B model) | 8 GB (3B model) |
| **System RAM** | 8 GB | 16 GB |
| **Disk** | 10 GB (model cache) | 20 GB |
| **CPU** | 4 cores | 8+ cores |

**CPU Inference**: Supported but slow (~30-60s per analysis). Set `AI_DEVICE=cpu`.

**Model Download**: First run downloads ~6GB (3B model) to HuggingFace cache (`~/.cache/huggingface` or `HF_CACHE_DIR`).

---

## Security

- No credentials in code — all via `.env`
- Input validation on all file paths (prevents path traversal)
- Media format/size validation
- CORS restricted to configured origins
- No user data sent to external services (fully local)

---

## Future Extensibility

### Adding New Models
1. Implement `BaseMultimodalModel` interface
2. Add to `get_model()` factory in `ai/models/__init__.py`
3. Update `.env.example` with new model option

### Adding New Modalities
1. Create `analyze_<modality>()` service
2. Add prompt template
3. Update `analyze_multimodal()` and `EventAnalyzer`
4. Extend `modality` field in database if needed

### Prompt Engineering
- Prompts in `ai/prompts/` — edit without code changes
- Version prompts alongside model changes
- Test with `pytest tests/test_ai_analysis.py`