# RESQ-AI Full-System Integration Notes

> Historical run record: the test counts and unavailable-database observations
> below predate the isolated PostGIS validation. Use the current
> [application acceptance report](./application_acceptance_report.md) for the
> latest test, startup, database, and workflow results.

## Reproducible local startup (PowerShell)

Run commands from the `resq-ai` directory.

1. Create and activate a backend virtual environment, then install the
   declared development and AI dependencies:

   ```powershell
   python -m venv backend\.venv
   .\backend\.venv\Scripts\Activate.ps1
   Push-Location .\backend
   pip install -e ".[dev,ai]"
   Pop-Location
   Copy-Item .env.example .env
   ```

2. Edit `.env`: set `DATABASE_PASSWORD` to a password you choose and set
   `COPILOT_PROVIDER=mock` if you do not have a local model server. Start
   PostgreSQL with PostGIS (the Docker Desktop daemon must be running):

   ```powershell
   docker run -d --name resq-ai-db -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=change_me -e POSTGRES_DB=resq_ai -p 5432:5432 postgis/postgis:15-3.4
   ```

   Set the `.env` value to the same password as the container.

3. From `resq-ai`, run the backend. The working directory must stay at this
   project root so the sibling `ai` package and `.env` file can be found:

   ```powershell
   python -m alembic -c .\backend\alembic.ini upgrade head
   python -m uvicorn --app-dir backend app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   Apply the versioned Alembic migrations after PostgreSQL/PostGIS is running
   and before starting the API. The application does not create or reset the
   database automatically.

4. In another terminal, start the React development server:

   ```powershell
   cd .\resq-ai\frontend
   npm install
   npm start
   ```

   Open `http://localhost:3000`; API docs are at `http://localhost:8000/docs`.

5. Optional sample-event loading, from the `resq-ai` root with the backend
   virtual environment active:

   ```powershell
   $env:PYTHONPATH = "$PWD\backend;$PWD"
   python .\data\load_sample_events.py
   ```

The local Copilot can use Ollama by setting
`COPILOT_PROVIDER=openai_compatible`, `COPILOT_API_BASE_URL=http://localhost:11434/v1`,
and `COPILOT_MODEL_NAME` to a model already pulled into Ollama. This does not
replace the separate Transformers model used for multimodal event analysis.

## Checks run in this workspace

| Check | Result |
|---|---|
| Initial backend baseline (`python -m pytest -q`) | 303 passed, 22 failed; failures traced to invalid async test fixture commits, missing test imports, route matching, mocked async methods, and latest-analysis selection |
| Focused analysis/geospatial API tests after corrections | 31 passed |
| Full backend suite after corrections (`python -m pytest -q`) | 327 passed, 149 warnings |
| Backend import smoke check using `backend` on the import path | Passed; 15 FastAPI routes registered |
| Python AST syntax parse of RESQ-AI sources | 108 files parsed; no syntax errors |
| Frontend production build (`npm run build`) | Passed with existing ESLint warnings in `LegacyConsole.jsx` and `MapView.js` |
| Frontend API client tests | 3 passed |
| Docker availability | Blocked: Docker Desktop daemon was not running |
| PostgreSQL availability | Blocked: no service accepted a connection on localhost:5432 |
| Live AI inference | Not run; no model server request made and no model weights downloaded |

The successful full backend suite used the machine's system Python, which had
the test dependencies installed. The repository-root `.venv` did not have
`pytest-asyncio` or FastAPI installed, so use the RESQ-AI backend installation
commands above before running these checks in a fresh environment.

## Workflow verification status

The unit and API tests exercise pieces of the system, but no deterministic
end-to-end test currently proves the full requested workflows:

- **A — event to incident:** individual event, analysis, and incident behavior
  has tests; the full persisted chain was not run as one workflow.
- **B — incident intelligence:** evidence and risk code has tests; a single
  end-to-end persisted run was not performed.
- **C — resource optimization:** recommendations and approval boundary have
  code/tests; database-backed optimization and allocation persistence were not
  exercised together.
- **D — copilot and dashboard:** copilot tool tests and dashboard tests pass;
  a browser-to-database grounded conversation was not performed.

## Database and geospatial limitations

SQLite fixtures allow ordinary database/API integration tests, but they use
minimal geometry shims only. Do not use these fixtures as evidence that
PostGIS-only spatial queries, spatial indexes, buffer geometry, distance
ordering, or GeoJSON conversion work. Run those checks against PostgreSQL with
PostGIS after a database service and migrations are available. Do not describe
nearby infrastructure as damaged unless a separate data source confirms
damage, and do not present straight-line distance as driving time.

## Known deployment and evaluation gaps

- No Docker Compose deployment, Dockerfiles, database backup/restore procedure,
  or tested readiness/dependency configuration is included.
- `Base.metadata.create_all` is used on startup; schema evolution needs
  versioned migrations before a production deployment.
- Real multimodal inference and live Copilot behavior have not been validated.
- No labeled evaluation dataset or model quality scores were produced.
- Frontend build warnings remain; browser console/network behavior has not been
  checked in an automated browser.
- This is a limited integration verification, not a complete security audit,
  regulatory review, or production-readiness certification.
