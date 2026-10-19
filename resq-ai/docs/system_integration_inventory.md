# RESQ-AI System Integration Inventory

This inventory records the current code paths and what has actually been
verified. Presence of a route or service is not evidence that a full workflow
has been exercised.

## Application components

| Component | Entry point / implementation | Integration status |
|---|---|---|
| FastAPI backend | `backend/app/main.py` | Imports successfully when run from `resq-ai` with `--app-dir backend`; route registration smoke-checked |
| Event analysis | `backend/app/api/analysis.py`, `ai/services/` | Mocked analysis API tests pass; live model inference not run |
| Incidents and investigation | `backend/app/api/incidents.py`, `backend/app/api/investigation.py`, `ai/services/` | Unit/API tests are included in the passing backend suite; complete event-to-investigation workflow not run |
| Geospatial services | `backend/app/api/geospatial.py`, `backend/app/services/geospatial_service.py` | Non-spatial API behavior is tested with SQLite and service mocks; spatial SQL needs PostGIS |
| Risk and resources | `backend/app/api/risk.py`, `backend/app/api/resources.py`, related services | Existing backend tests pass; full incident-to-resource workflow not run |
| Optimization | `backend/app/api/optimization.py`, `backend/app/optimization/` | Code and tests are present; persisted recommendation workflow was not end-to-end tested |
| Copilot | `backend/app/api/copilot.py`, `backend/app/ai/` | Deterministic fake/mock tests pass; live Ollama or other model server not tested |
| Command center | `backend/app/api/dashboard.py`, `frontend/src/pages/` | Backend suite and frontend production build pass; browser-driven workflow not run |
| React frontend | `frontend/src/App.js`, `frontend/src/api/client.js` | Production build passes with lint warnings; three API client tests pass |

## Database and model layer

SQLAlchemy models are in `backend/app/models/` and include events, analyses,
incidents, evidence, infrastructure, risks, resources, optimization results,
and copilot conversations. The configured production database is PostgreSQL
with PostGIS, using `DATABASE_*` settings from `.env`.

Application startup currently calls `Base.metadata.create_all`. No Alembic
configuration or migration revisions were found under `backend/`; this is not
a substitute for reviewed, versioned schema migrations.

SQLite test fixtures install limited geometry type/function shims. They do not
emulate PostGIS distance, buffer, intersection, or spatial index behavior.
There is no PostgreSQL/PostGIS service available in the current environment,
so those operations remain unverified here.

## Local model integration

The copilot supports an OpenAI-compatible endpoint through
`COPILOT_PROVIDER=openai_compatible`, `COPILOT_API_BASE_URL`,
`COPILOT_MODEL_NAME`, and optional `COPILOT_API_KEY`. Ollama is a supported
local server. `COPILOT_PROVIDER=mock` is deterministic and offline; it is not
live model inference. Event image/video analysis uses the separate
Transformers-based analyzer configured by `AI_*` environment settings.

No real inference request was made and no model weights were downloaded during
this verification.

## Deployment inventory

- `frontend/package.json` provides start, build, and test scripts.
- PostgreSQL/PostGIS can be started manually with the documented Docker
  command, but Docker Desktop was unavailable during verification.
- No Compose file or Dockerfiles were found.
- Persistent volumes, container health checks, database backups, and tested
  migrations are not currently provided.

## Verified checks

See [full_system_integration.md](./full_system_integration.md) for commands,
results, and environment limitations. See
[project_completion_audit.md](./project_completion_audit.md) for the concise
status summary.
