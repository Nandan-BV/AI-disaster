# RESQ-AI Frontend/Backend Repair Report

> Historical repair-run results below predate the isolated PostGIS acceptance
> run. Their database-unavailable, test-failure, and browser observations are
> superseded by the current [application acceptance report](./application_acceptance_report.md)
> and [project fixes needed report](./project_fixes_needed_report.md).

## Diagnosis and fixes

The blank-page failures were not caused only by missing records:

- `frontend/package.json`, `frontend/src/App.js`, and several backend Python
  modules contained literal Git conflict markers. npm could not parse the
  manifest, and Python could not import the backend settings. The app entry
  point also had two competing implementations appended together.
- The routed dashboard implementation calls the intended wrapped API
  responses, but the Resources page treated `GET /resources` as a raw array
  instead of reading the `resources` member of `ResourceListResponse`.
- The Command Center dereferenced dashboard arrays when the API request failed,
  causing an uncaught runtime exception. It now shows explicit unavailable
  states and does not display unavailable resource totals as zero.
- The Live Map returned a loading placeholder before mounting its map container,
  so MapLibre never received an element. Infrastructure feature keys did not
  match layer keys, visibility changes used stale state, and optional layer
  failures had no visible message. The map now mounts consistently, validates
  WGS84 coordinates and GeoJSON, toggles data-backed layers, and reports
  basemap/API failures.
- PostGIS `ST_AsGeoJSON` output was inserted into a GeoJSON geometry without
  parsing its JSON string. Incident coordinates at zero were also treated as
  absent. Both cases are now handled.
- Risk rendering requested `environmental_component`, while the backend schema
  returns `environment_component`; assessment and impact request errors are now
  visible as well.

No database was reset or seeded. No synthetic events, incidents, resources, or
assessments were created.

## Files changed

- `frontend/package.json`
- `frontend/src/App.js`
- `frontend/src/App.css`
- `frontend/src/MapView.js`
- `frontend/src/pages/CommandCenter.jsx`
- `frontend/src/pages/EventsPage.jsx`
- `frontend/src/pages/IncidentsPage.jsx` (regression test only)
- `frontend/src/pages/LiveMapPage.jsx`
- `frontend/src/pages/ResourcesPage.jsx`
- `frontend/src/pages/RiskPage.jsx`
- `frontend/src/MapView.test.js`
- `frontend/src/pages/CommandCenter.test.jsx`
- `frontend/src/pages/EventsPage.test.jsx`
- `frontend/src/pages/IncidentsPage.test.jsx`
- `frontend/src/pages/ResourcesPage.test.jsx`
- `frontend/src/pages/RiskPage.test.jsx`
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/api/health.py`
- `backend/app/api/resources.py`
- `backend/app/services/geospatial_service.py`
- `backend/tests/test_geospatial_map_data.py`
- `backend/tests/test_health_unavailable.py`
- `ai/services/evidence_collector.py`
- `README.md`
- `docs/full_system_integration.md`

## API and database verification

The backend imported and started after the missing declared runtime packages
(`bcrypt`, `PyJWT`, and `sse-starlette`) were installed into the existing
backend virtual environment. OpenAPI returned HTTP 200 and confirmed these
routes are registered:

- `GET/POST /api/v1/events`
- `GET /api/v1/incidents`
- `GET /api/v1/dashboard/incidents/summary`
- `GET /api/v1/dashboard/overview`
- `GET /api/v1/incidents/{incident_id}/map-data`
- Risk, impact, resources, health, and copilot endpoints used by the UI

The configured database is PostgreSQL with PostGIS-backed geospatial queries.
The database connection was refused in this environment. During initial
smoke-testing, health and data requests returned HTTP 500 because the driver
surfaced `ConnectionRefusedError` outside the health endpoint's SQLAlchemy
exception handler. Health now handles connection errors explicitly and returns
HTTP 503 with a degraded status, covered by a focused regression test. Data
requests to `/events`, `/incidents`, and `/resources` still cannot return
records. Therefore, real response rows, current migrations, and live PostGIS
behavior could not be verified. The database was not altered.

## Tests and builds

Passed:

- `cd frontend; npm test -- --watchAll=false --runInBand` — 7 suites, 13 tests
- `cd backend; .\.venv\Scripts\python.exe -m pytest -q tests\test_geospatial_map_data.py tests\test_health_unavailable.py` — 2 tests
- `cd frontend; npm run build` — production build succeeds

The production build still reports existing ESLint warnings in
`frontend/src/LegacyConsole.jsx`; no warning was reported for the repaired
pages or map component.

The full backend test command
`.\.venv\Scripts\python.exe -m pytest -q` is not green: 8 failures, 11 passes,
and 18 errors in the existing `backend/tests/test_resource.py` suite. Those
tests refer to stale resource enum values and signatures and have mismatched
mock/fixture setup (including an undefined `ResourceStatusUpdate`). The
project-level test collection also fails on unresolved conflict markers in
legacy test modules and missing `aiosqlite`; these test-only issues were not
rewritten as part of the application repair.

## Browser smoke test

The integrated browser opened the app and visited `/`, `/incidents`, `/events`,
`/map`, `/risk`, `/resources`, `/optimization`, `/copilot`, and
`/system-status`. All pages rendered their main content with **zero uncaught
page errors** while the database was unavailable; data-dependent pages
displayed their request error/unavailable states.

The map container/mount path was covered by a frontend regression test. A
map with real database features and successful external OpenStreetMap tiles
could not be visually verified because the database was unavailable.

## Remaining blockers

- Start the configured PostgreSQL/PostGIS database and apply migrations before
  expecting data endpoints to return application data.
- Repair the existing backend resource tests and conflicted legacy test modules
  before relying on the full Python suite.
- Verify live data, database response schemas, PostGIS map features, and external
  basemap availability in an environment with the database and network access.
- The local Copilot model/service was not exercised in this smoke test.

## VS Code startup commands

Start PostgreSQL/PostGIS first, and ensure `resq-ai/.env` contains the matching
database settings. In a VS Code terminal rooted at `resq-ai`, apply migrations
and start the backend:

```powershell
.\backend\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head
.\backend\.venv\Scripts\python.exe -m uvicorn --app-dir backend app.main:app --reload --host 0.0.0.0 --port 8000
```

In a second VS Code terminal:

```powershell
cd .\frontend
npm start
```

Then open `http://localhost:3000`. If the backend virtual environment or
frontend packages have not been installed yet, follow the dependency setup in
the project README before running these commands.
