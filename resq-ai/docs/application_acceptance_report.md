# RESQ-AI Application Acceptance Report

**Run date:** 2026-10-20  
**Result:** **NOT ACCEPTED for a complete data-backed demonstration**

## Executive summary

The API and frontend development server started against a disposable,
isolated PostgreSQL 15.8/PostGIS 3.4.3 database. Alembic migrations completed
through `20261010_0003` (head). The health endpoint reported a connected
database; dashboard, events, incidents, resources, infrastructure, and Copilot
tool-catalog requests returned HTTP 200. A synthetic event was created and
read back from the database. A synthetic resource was retrieved through the
nearby-resource PostGIS query at **216.93 m**.

The rest of the primary workflow could not be accepted. Event analysis and
incident clustering depend on AI model weights that are not present in the
local model cache. The configured local Qwen model produced text, but did not
produce the structured tool calls the Copilot needs; the application now
refuses to present unsupported text as a grounded answer. No incident was
created, so investigation, evidence, risk/impact, optimization, and human
approval could not be exercised with a real workflow record.

No connected browser client was available. HTTP requests to frontend paths
returned the React app shell, but that is not evidence that each page rendered
its data or that the map, browser console, tile service, and visual states
work. Consequently this report accepts the verified API/database checks and
automated suites, but does **not** accept all user-facing pages or the complete
event-to-approval workflow. This is not a production-readiness assessment.

## Startup and environment

| Check | Result | Evidence |
|---|---|---|
| Backend startup | PASS | Uvicorn served `127.0.0.1:8000`; OpenAPI returned HTTP 200. |
| Frontend startup | PASS | React development server served `127.0.0.1:3000`; compile succeeded. |
| Frontend API target | PASS | Development-server proxy points to `http://localhost:8000`; `frontend/package.json` matches. |
| Frontend route fallback | PASS, limited | Requests with browser-like `Accept: text/html` to `/`, `/events`, `/incidents`, `/map`, `/investigations`, `/risk`, `/resources`, `/optimization`, `/copilot`, and `/system-status` returned HTTP 200. This confirms the app shell only, not page behavior. |
| Health | PASS | `GET /api/v1/health` returned HTTP 200: database `connected`, Copilot provider `available`. Provider availability does not prove tool calling works. |
| Separate readiness endpoint | NOT PROVIDED | `GET /api/v1/ready` returned HTTP 404; health is the only observed health route. |
| Database connectivity | PASS | Isolated PostGIS test database accepted API reads and writes. |
| Migrations | PASS | `alembic upgrade head` completed; `alembic current` reported `20261010_0003 (head)`. |
| Migration drift check | NOT RELIABLE | `alembic check` reported differences involving PostGIS extension/TIGER objects in the shared `public` schema; it was not used as evidence of application-schema drift. |
| Startup log quality | PASS with warnings | Services started and served requests. SQLAlchemy emitted model warnings for ORM attributes named `metadata`; React build/start output contains existing lint/deprecation warnings. |
| Database isolation | PASS | Validation used a disposable PostGIS container on port 55432 and a dedicated `resq_ai_acceptance` database, not the configured application database. |

## Page-by-page verification

The table distinguishes API evidence from browser acceptance. **UI render,
empty/error presentation, and browser JavaScript errors were not observed**
because no browser client was connected. The final status therefore does not
upgrade an API pass into a page pass.

| Page / route | API requests and HTTP statuses | Actual data / empty state | Error state / JavaScript | Result |
|---|---|---|---|---|
| Dashboard — `/` | `GET /api/v1/dashboard/overview` — 200; `GET /api/v1/dashboard/incidents/summary` — 200 | Dashboard payload returned from PostGIS; incident counts were empty/zero because no incident was created. UI rendering not observed. | Browser error/retry presentation and console not observed. | **BLOCKED** — API verified; browser page not verified. |
| Events — `/events` | `GET /api/v1/events` — 200; synthetic event read by ID — 200; `GET /api/v1/events/{id}/analysis` — 404 (no analysis stored). | A synthetic acceptance event was persisted and returned by the API. UI row/empty-state rendering not observed. | Browser error/retry presentation and console not observed. | **BLOCKED** — event persistence passes; analysis and browser page are not accepted. |
| Incidents — `/incidents` | `GET /api/v1/incidents` — 200 | Successful empty list; no incident was generated. UI empty-state rendering not observed. | Browser state and console not observed. | **BLOCKED** — API empty response verified; page not verified. |
| Incident detail — `/incidents/{incidentId}` | Read for an unused UUID — 404. | No persisted incident/detail record exists. | Browser page behavior not observed. | **BLOCKED** — no incident fixture or browser run. |
| Live Map — `/map` | `GET /api/v1/incidents` — 200 empty; infrastructure listing — 200; map-data request for an unused incident — 404. | No incident feature was available. The API cannot establish that a mounted map, basemap, markers, and overlays render correctly. | Container dimensions, tile loading, invalid-coordinate display, and browser errors not observed. | **BLOCKED** — no incident fixture and no browser-based map acceptance. |
| Evidence / investigation — `/investigations` | Incident list — 200 empty; evidence request for an unused incident — 404 after fixing the route's missing SQLAlchemy import. | No evidence or investigation could be retrieved because no incident was generated. UI empty state not observed. | Before the fix, the evidence endpoint returned 500; regression tests now verify the expected 404. Browser state/console not observed. | **BLOCKED** — endpoint missing-record handling fixed; workflow and page not verified. |
| Risk and impact — `/risk` | Incident list — 200 empty; risk, impact, and risk-history reads for an unused incident — 404. | No risk/impact assessment exists without an incident. UI state not observed. | Browser state/console not observed. | **BLOCKED** — no incident fixture; page not verified. |
| Infrastructure — integrated, no separate navigation route | `GET /api/v1/incidents/infrastructure` — 200 | API listing was available; no live map overlay was verified. | No dedicated infrastructure page exists; browser map behavior not observed. | **BLOCKED** — API available; map integration not accepted. |
| Resources — `/resources` | `GET /api/v1/resources` — 200; `GET /api/v1/resources/nearby` — 200 | Synthetic hospital resource was persisted and returned at 216.93 m from the test coordinate. UI inventory and nearby display not observed. | Browser state/console not observed. | **BLOCKED** — API and PostGIS distance verified; page not verified. |
| Resource optimization — `/optimization` | No optimization was run. Reads for an unused incident return 404. | No recommendation or allocation exists because there is no incident workflow record. | Human-review UI and browser console not observed. | **BLOCKED** — prerequisite incident absent. |
| AI Copilot — `/copilot` | `GET /api/v1/copilot/tools` — 200. A live Copilot query against the local Qwen server returned the fail-closed message rather than an ungrounded answer. | No grounded answer/tool trace was produced; the model skipped structured tool calls. UI rendering not observed. | No browser console available; safe failure is observed at the service/API layer. | **FAIL** — local model/provider does not satisfy the Copilot tool-calling requirement. |
| System Status — `/system-status` | `GET /api/v1/health` — 200; dashboard overview — 200; Copilot tool catalog — 200. | API health reports the database connected and model endpoint available; this does not verify Copilot tool calling. UI status display not observed. | Browser presentation/console not observed. | **BLOCKED** — API health verified, page not verified. |

### Live Map acceptance

The route shell and map-data API were reachable, and the map-related regression
tests passed. The acceptance database had no incident, so there was no real
incident feature to compare against rendered markers. A connected browser was
not available to measure the rendered map container, verify the configured
OpenStreetMap raster basemap requests, inspect marker/layer correspondence, or
exercise malformed coordinates and visible map-configuration errors.
**Live Map is not accepted.**

## API and database verification

| Endpoint / operation | Result | Evidence |
|---|---|---|
| `GET /openapi.json` | HTTP 200 | API schema served. |
| `GET /api/v1/health` | HTTP 200 | Database connected; Copilot endpoint/model marked available. |
| `GET /api/v1/ready` | HTTP 404 | No separate readiness route. |
| Dashboard overview and incident summary | HTTP 200 | Database-backed overview and summary responses returned. |
| Event create, list, and retrieve | PASS | Authenticated synthetic event write succeeded and was read back from the isolated database. |
| Event analysis | NOT RUN | Required local AI analysis/embedding weights were not available; no model download was started. |
| Incident processing / clustering | PARTIAL | Candidate-event PostGIS query executed after fixing datetime-module shadowing and returned zero candidates for a database containing only the current synthetic event. No incident was created. |
| Resource create and list | PASS | Synthetic resource was persisted and returned by the collection API. |
| Nearby resource query | HTTP 200 | PostGIS distance returned the test hospital at 216.93 m. |
| Infrastructure listing | HTTP 200 | Listing route returned successfully; no map overlay was visually tested. |
| Evidence for missing incident | HTTP 404 after fix | A prior 500 came from `select` being undefined in the endpoint; the import was fixed and route regression tests pass. |
| Copilot tools catalog | HTTP 200 | Tool metadata is available; it is not proof of usable model tool calls. |
| Copilot answer | FAIL / safely blocked | Local model text inference works, but the model did not emit required tool calls. Fail-closed behavior avoids presenting unsupported output as grounded. |

## Data-driven workflow

**Result: PARTIAL; the complete workflow is not accepted.** All writes and
queries below used only the disposable acceptance database.

| Stage | Result |
|---|---|
| Event creation → persistence → retrieval | PASS; synthetic event was written and read back. |
| Event analysis | BLOCKED; the required local AI weights are not cached, and no model download was attempted. |
| Incident creation/update | BLOCKED; the supported analysis/clustering handoff could not be completed. The candidate-event query itself now executes against PostGIS. |
| Evidence retrieval | BLOCKED for workflow; missing-incident behavior now correctly returns 404, but no incident/evidence record exists. |
| Risk and impact assessment | BLOCKED; requires a persisted incident. |
| Resource retrieval | PASS; synthetic resource and nearby distance were returned from PostGIS. |
| Optimization recommendation | NOT RUN; no incident/risk/demand fixture exists. |
| Human review of allocation | NOT RUN; no allocation was created. |
| Copilot query grounded in workflow records | FAIL / safely blocked; model did not call data tools, and no incident exists to ground a response. |

## Automated checks

| Check | Result |
|---|---|
| Root backend suite: `python -m pytest .\tests -q` | **PASS — 353 passed, 156 warnings.** |
| Backend-local geospatial and unavailable-health tests | **PASS — 2 passed, 31 warnings.** |
| Focused clustering/evidence regression tests | **PASS — 58 passed, 31 warnings.** |
| Frontend tests: `npm test -- --watchAll=false --runInBand` | **PASS — 8 suites, 18 tests.** |
| Frontend production build: `npm run build` | **PASS** with existing unused-variable/redundant-alt ESLint warnings in `LegacyConsole.jsx`. |
| PostGIS migration and live spatial checks | **PASS for exercised operations** — migration head, event persistence, nearby-resource distance, candidate-event query. |
| Browser E2E | **NOT TESTED** — no connected browser client or configured E2E runner was available for this run. |

Warnings include Pydantic configuration deprecations, SQLAlchemy ORM
`metadata`-attribute warnings, React Router future flags, development-server
deprecations, and existing `LegacyConsole.jsx` lint warnings. The warnings did
not fail the test/build commands.

## Outstanding bugs, risks, and configuration requirements

| Severity | Finding | Effect / required next action |
|---|---|---|
| **High — demonstration blocker** | Local Qwen Copilot model does not emit required structured tool calls. | Select and validate a function-calling-compatible provider/model, then verify a grounded answer and successful tool trace against a known incident. |
| **High — workflow blocker** | Analysis/embedding model weights are not present locally. | Provision the required model artifacts in the demonstration environment and run event analysis → clustering without downloading during a smoke test. |
| **High — acceptance blocker** | No incident was created, so investigation, evidence, risk/impact, optimization, and human-review transitions remain unverified. | Complete the supported event-to-incident chain using isolated fixtures and verify each persisted handoff before demonstration. |
| **High — UI acceptance blocker** | No connected browser client was available. | Run real browser acceptance for each route, empty/error/loading states, uncaught JavaScript errors, map dimensions, tiles, and marker/data correspondence. |
| **Medium** | No standalone infrastructure page or separate readiness endpoint exists. | Confirm these are accepted product-scope choices or implement them; current infrastructure is exposed through map/API surfaces, and health is the only readiness-like route. |
| **Low** | ORM models use an attribute named `metadata`; frontend build and router emit existing warnings. | Rename ORM Python attributes safely (preserving DB column names), and clean existing frontend warnings in a separate maintenance pass. |

## Exact startup commands

The documented local setup is run from `resq-ai/` in PowerShell. The database
command below uses the README's default port; set `.env` credentials to match.
The acceptance run used an equivalent disposable database on port 55432 instead
of writing to a developer database.

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
Push-Location .\backend
pip install -e ".[dev,ai]"
Pop-Location
Copy-Item .env.example .env

docker run -d --name resq-ai-db `
  -e POSTGRES_USER=postgres `
  -e POSTGRES_PASSWORD=change_me `
  -e POSTGRES_DB=resq_ai `
  -p 5432:5432 postgis/postgis:15-3.4

# Set DATABASE_PASSWORD=change_me in .env, then:
python -m alembic -c .\backend\alembic.ini upgrade head
python -m uvicorn --app-dir backend app.main:app --reload --host 0.0.0.0 --port 8000
```

In a second PowerShell terminal from `resq-ai/`:

```powershell
Push-Location .\frontend
npm install
npm start
```

Open `http://localhost:3000`; the API docs are at `http://localhost:8000/docs`.
For real Copilot tool use, configure a tested tool-calling provider; a running
Ollama text endpoint alone is not sufficient. See
[Ollama setup](./ollama_setup.md).

## Conclusion

**RESQ-AI is not yet accepted for a complete data-backed demonstration.**
The database migrations, event persistence, resource lookup, PostGIS distance
query, health/API checks, backend/frontend tests, and frontend build pass.
However, AI-driven event analysis, incident creation, the downstream evidence
and risk/optimization workflow, actual browser page rendering, live map
features, human approval, and grounded Copilot tool use remain unverified or
blocked. Do not claim production readiness.
