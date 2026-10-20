# RESQ-AI Project Fixes Needed

**Updated:** 2026-10-20  
**Evidence source:** [Application acceptance report](./application_acceptance_report.md)  
**Decision:** Core API/database checks and automated suites pass, but the
application is **not accepted for a complete data-backed demonstration**.

## Executive summary

The earlier database-unavailable assessment is superseded. A disposable
PostgreSQL/PostGIS instance was provisioned; migrations reached head, event and
resource persistence worked, and the nearby-resource PostGIS query returned a
real distance. A full root backend run now passes, as do the frontend suite and
production build.

The remaining blockers are functional rather than startup/connection issues:
the local Copilot model does not issue the tool calls required to retrieve
grounding data; event analysis/embedding model weights are unavailable; and
therefore the incident-to-investigation/risk/optimization/human-review chain
has not been run. Browser-based page and Live Map acceptance is also still
blocked because no browser client was connected.

## Prioritized fixes and acceptance criteria

| Priority | Area | What still needs to be fixed or completed | Acceptance criteria |
|---|---|---|---|
| **P0 — demonstration blocker** | Grounded Copilot | Replace or reconfigure the local model/provider with one that returns the structured tool calls this API supplies. The current Qwen server returns text but not usable tool calls; the backend safely fails closed. | Ask a question about a known persisted incident; verify the expected read-only tools run, the returned answer cites the actual source records, and the safe tool trace is accurate. |
| **P0 — workflow blocker** | AI model assets | Make the configured event-analysis and embedding model weights available to the demo/test environment. The Qwen VL analysis and BGE embedding weights were not present in the local cache; no download was triggered. | Run event analysis and clustering from locally available, documented weights; confirm no hidden first-request download blocks or breaks the workflow. |
| **P1 — acceptance blocker** | Persisted end-to-end workflow | Complete and verify event → analysis → incident creation/link → evidence investigation/retrieval → risk/impact → resources → optimization → human allocation review. Event persistence and resource proximity alone do not prove the downstream chain. | Each stage returns the expected IDs/state and persists them in a disposable PostGIS database; tests verify both successful transitions and missing-record behavior. |
| **P1 — acceptance blocker** | Browser page acceptance | Use a connected browser to exercise every implemented route with data, empty collections, and API failures; capture browser console errors. Current route HTTP 200 responses only prove that the frontend app shell is served. | Dashboard, Events, Incidents/detail, Live Map, Evidence, Risk, Resources, Optimization, Copilot, and System Status show their intended content and clear loading/empty/error states without uncaught JavaScript errors. |
| **P1 — acceptance blocker** | Live Map | Validate a real incident and infrastructure dataset against rendered features and configured OSM tiles. The acceptance database had no incident, and no browser inspection was possible. | Measure a nonzero map container; verify basemap/tile requests, marker/feature coordinates, layer visibility, zero coordinates, invalid coordinates, missing configuration, and API data correspondence in a browser. |
| **P2 — reliability** | Automated end-to-end coverage | Add a repeatable browser E2E command/runner for the highest-value flow. Existing checks are unit/component/API tests; no E2E command is configured in the frontend scripts. | CI/local E2E covers creation, persistence, errors/empty states, map behavior, optimization recommendation, and operator approval using isolated data and safe teardown. |
| **P2 — product scope** | Infrastructure and readiness destinations | Decide whether the integrated infrastructure/map surface and health endpoint are sufficient. There is no standalone infrastructure navigation page or `/ready` endpoint; `/api/v1/ready` returns 404. | Document and test the chosen product contract, or implement separately scoped pages/endpoints with truthful health/readiness semantics. |
| **P3 — maintenance** | Existing warnings | Clean SQLAlchemy warnings caused by Python ORM attributes named `metadata` (without renaming the database columns), Pydantic config deprecations, and existing `LegacyConsole.jsx` lint and React Router/development-server warnings. | Keep tests/build passing and eliminate or explicitly suppress only understood warnings. |

## Fixes completed and verified

These are no longer outstanding items:

- Resolved test and source merge-conflict damage; the full root backend suite
  now collects and passes.
- Fixed duplicate GeoAlchemy-managed spatial indexes in the initial migration;
  the isolated PostGIS database migrated through `20261010_0003`.
- Normalized timezone-aware event timestamps for the database's
  timezone-naive timestamp column; event creation/readback passed.
- Replaced invalid string spatial casts with GeoAlchemy `Geography`/`Geometry`
  types; live resource proximity returned the expected 216.93 m distance.
- Fixed datetime module shadowing in candidate-event filtering; the live
  PostGIS query now executes without a Python exception.
- Fixed missing SQLAlchemy `select`/`func` imports in investigation API routes;
  missing-incident evidence/investigation checks now return 404 instead of 500.
- Exposed database outages as degraded health/503, and made sidebar status
  derive from backend health instead of asserting the system is always
  operational.
- Made Copilot fail closed if the model returns text without retrieving
  supporting RESQ-AI records.
- Corrected frontend/API mismatches and map/risk/resource rendering issues
  documented in the [frontend/backend repair report](./frontend_backend_repair_report.md).

Regression tests cover these changes. Do not revert them when addressing the
remaining AI-model, browser, or workflow work.

## Current verification snapshot

| Check | Result |
|---|---|
| Root backend tests | **353 passed**, 156 warnings. |
| Backend-local map/health tests | **2 passed**, 31 warnings. |
| Frontend tests | **8 suites, 18 tests passed.** |
| Frontend production build | **Passed**; existing `LegacyConsole.jsx` lint warnings remain. |
| PostGIS migration | **Passed**; current revision `20261010_0003 (head)`. |
| Event persistence | **Passed** in the isolated acceptance database. |
| Resource retrieval and PostGIS proximity | **Passed**; sample resource returned at 216.93 m. |
| Live health/API | **Passed** for exercised APIs; `/api/v1/ready` is not implemented. |
| Copilot tool calling | **Failed for the configured model**; safe fail-closed response works. |
| Event-to-human-review workflow | **Not completed**; model assets and incident records are prerequisites. |
| Page-by-page browser / live map acceptance | **Blocked**; no connected browser client. |

## Recommended execution order

1. Select a tool-calling-capable Copilot provider and verify real tool use on a
   known persisted incident.
2. Provision the required analysis and embedding weights in the demo
   environment; run analysis and clustering without surprise downloads.
3. Repeat the full persisted workflow in a newly isolated disposable PostGIS
   database, including evidence, risk/impact, optimization, and human review.
4. Run browser acceptance for all routes and the Live Map; save console/network
   evidence and exercise successful, empty, malformed, and failure states.
5. Add an automated E2E check for the critical event-to-review journey.
6. Decide whether dedicated infrastructure and readiness routes are required.
7. Triage the non-blocking ORM/deprecation/lint warnings.

## Readiness decision

**Not ready for a complete data-backed demonstration.** The database,
migrations, core API checks, event/resource persistence, PostGIS resource
distance, and automated unit/component checks are verified. Real analysis and
grounded Copilot use are not; the incident-to-human-review flow and browser
pages/map have not been accepted. This conclusion is not a production
readiness assessment.
