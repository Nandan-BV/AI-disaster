# Phase 10 — Emergency Command Center Dashboard

The command center is a single operator workspace that brings together every
phase of RESQ-AI (events, AI analysis, incident clustering, evidence
investigation, geospatial, risk & impact, resources, optimization, and the
copilot) behind one routed React app and two read-only aggregation endpoints.

The dashboard **integrates** the existing phases. It does not re-implement any
of them: no re-clustering, no re-scoring, no re-optimization, no new AI
call. Every number it shows comes from data an earlier phase already produced.

---

## Principles

1. **Backend is the source of truth.** All figures come from real database
   queries. The frontend never fabricates or estimates a value.
2. **No duplication.** The dashboard calls existing endpoints
   (`/incidents`, `/risk-assessment`, `/investigation-summary`,
   `/optimization`, `/copilot/...`). The only new code is aggregation.
3. **Explicit gaps.** When a phase has not produced data yet (for example, no
   risk assessment for an incident), the UI shows an "unavailable" state
   rather than a misleading `0`.
4. **Human-in-the-loop is preserved.** The dashboard can trigger *analysis*
   runs and lets an operator **approve or reject** resource allocations, but it
   never auto-dispatches and the copilot still cannot approve anything.
5. **Polling, not streaming.** The backend has no push channel. The landing
   page refreshes on an interval (`DASHBOARD_REFRESH_INTERVAL_SECONDS`,
   default 30s); this is periodic refresh, not a live feed.

---

## Backend

### Endpoints

```
GET /api/v1/dashboard/overview?limit_recent=20
GET /api/v1/dashboard/incidents/summary?status=&risk_level=&incident_type=&search=&sort_by=&order=&limit=&offset=
```

#### `GET /dashboard/overview`

Aggregated landing-page payload. Assembled by `build_overview_payload`
(pure) from data gathered by `gather_overview` (read-only, fixed query order).

Response shape (`app/schemas/dashboard.py`):

```json
{
  "generated_at": "2026-10-10T12:00:00Z",
  "incident_metrics": {
    "total": 12, "active": 7, "emerging": 2, "resolved": 1,
    "critical_risk": 3, "high_risk": 2, "recently_updated": 4,
    "with_unmet_demand": 1
  },
  "event_metrics": { "total": 100, "analyzed": 70, "awaiting_analysis": 30, "recent_24h": 40 },
  "resource_metrics": { "total": 8, "available": 5, "deployed": 2, "unavailable": 0, "maintenance": 0, "unknown": 1 },
  "optimization_metrics": { "incidents_with_optimization": 4, "pending_approvals": 2, "approved_allocations": 3 },
  "recent_incidents": [ { "id": "…", "title": "…", "status": "active", "risk_score": 85.0, "risk_level": "critical", "event_count": 3, "…": "…" } ],
  "recent_events":    [ { "id": "…", "source": "social_media", "analysis_status": "completed", "…": "…" } ],
  "pending_approvals":[ { "allocation_id": "…", "incident_title": "…", "resource_name": "…", "distance_meters": 1200.0 } ]
}
```

Notable correctness points:

* `with_unmet_demand` counts only incidents whose **latest** optimization run
  still has a non-empty `unmet_demand`. The optimizer stores `[]` when demand
  is met, so a bare `is not None` check would over-count.
* `incidents_critical` / `incidents_high` count **distinct** incidents that
  have any assessment at that level.
* Recent incidents are enriched with their latest risk assessment and
  investigation summary; `risk_level` is `null` when no assessment exists.
* Recent events use explicit columns (no PostGIS geometry) and carry an
  `analysis_status` of `completed` or `pending`.

#### `GET /dashboard/incidents/summary`

Filterable, sortable, paginated incident list for the Incidents panel.

| Param | Notes |
|-------|-------|
| `status` | `emerging` \| `active` \| `resolved` |
| `risk_level` | `low` \| `moderate` \| `elevated` \| `high` \| `critical` |
| `incident_type` | free text |
| `search` | matches title or type (case-insensitive) |
| `sort_by` | `last_updated` \| `risk_score` \| `event_count` |
| `order` | `asc` \| `desc` |
| `limit` / `offset` | pagination (bounded by config) |

Invalid values for `status`, `risk_level`, `sort_by`, or `order` return `422`
before any database work.

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DASHBOARD_REFRESH_INTERVAL_SECONDS` | 30 | Frontend polling cadence (>= 5) |
| `DASHBOARD_DEFAULT_PAGE_SIZE` | 20 | Default page size for summary/overview |
| `DASHBOARD_MAX_PAGE_SIZE` | 100 | Upper bound for `limit` |

### Files

```
backend/app/api/dashboard.py       # routes + pure aggregation helpers
backend/app/schemas/dashboard.py   # response models
backend/app/config.py              # DASHBOARD_* settings
backend/app/main.py                # router registration
tests/test_dashboard.py            # aggregation + validation tests
```

---

## Frontend

The app was converted from a single monolithic tab component into a routed
command center. Layout components (`DashboardLayout`, `Sidebar`, `TopNav`)
provide the shell.

### Routes

| Path | Page |
|------|------|
| `/` | Command Center landing (metrics + panels) |
| `/incidents` | Incidents list (filters, search, pagination) |
| `/incidents/:incidentId` | Incident workspace (tabs) |
| `/events` | Events list + submit + analysis |
| `/map` | Live map |
| `/investigations` | Evidence investigations |
| `/risk` | Risk & impact |
| `/resources` | Resource inventory |
| `/optimization` | Optimization + approval decision |
| `/copilot` | AI copilot |
| `/system-status` | Backend health, volumes, copilot tools |
| `/console` | Legacy single-page console (lazy-loaded, unchanged) |

### Shared building blocks

```
frontend/src/api/client.js                 # fetch wrapper, ApiError (status + detail)
frontend/src/api/useAsyncData.js           # GET hook exposing { data, loading, error, status, reload }
frontend/src/components/common/StateViews.jsx  # Loading / Error / Empty / Unavailable
frontend/src/utils/format.js               # date, number, percent, distance, colour helpers
frontend/src/pages/pages.css               # shared page styling
```

`useAsyncData` exposes `status` so pages can distinguish a genuine `404`
("this phase has not produced data yet") from a transport error — the former
renders an `UnavailableState`, not an error.

### Incident workspace

`/incidents/:incidentId` is the deepest integration point, with tabs that pull
from each phase:

* **Overview** — incident detail + latest risk snapshot.
* **Evidence** — investigation summary + categorized evidence + run investigation.
* **Risk & Impact** — risk score and component bars, impact counts, run assessment.
* **Resources** — optimization result, allocations with **Approve/Reject**
  (calls `PATCH /incidents/resource-allocations/{id}/status`), nearby resources.
* **Map** — MapLibre view of the incident's analysis area and infrastructure.
* **Copilot** — the Phase 9 copilot panel scoped to this incident.

---

## Testing

`tests/test_dashboard.py` covers:

* pure helpers (`_text_preview`, `_has_unmet_demand`, `_latest_by_incident`);
* `build_overview_payload` / `build_incidents_summary_payload`, including the
  empty-database case and the `awaiting_analysis` derivation (never negative);
* `gather_overview` against a stub async session, verifying resource bucket
  mapping, unmet-demand counting, and serialization;
* route validation (`422`) for bad query parameters, which runs before any
  database access.

Run:

```bash
python -m pytest tests/test_dashboard.py -v
```

The tests use a stub session rather than a live database, for the same reason
the Phase 5/6 API tests do: the in-memory SQLite used by the suite cannot
create PostGIS geometry columns. This is a **pre-existing** limitation, not
specific to Phase 10.

---

## Known limitations

* The dashboard reflects the latest stored results; it does not push updates.
* The incident summary does not expose per-incident unmet-demand as a filter
  (only the aggregate count on the overview). Unmet-demand work is surfaced via
  the Optimization page.
* Approval decisions are recorded on the allocation record only; the dashboard
  does not model multi-step dispatch workflows.
