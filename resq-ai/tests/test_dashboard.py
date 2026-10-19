"""
Phase 10: Command Center dashboard tests.

The environment used by the rest of the suite cannot create PostGIS geometry
tables on SQLite (see the pre-existing ``test_events``/``test_geospatial_api``
failures), so these tests target the dashboard's pure aggregation layer plus a
stub session for the database-gathering path. No live database is required.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dashboard import (
    _has_unmet_demand,
    _text_preview,
    build_incidents_summary_payload,
    build_overview_payload,
    gather_overview,
)
from app.main import app
from app.models.incident import IncidentStatus
from app.models.resource import ResourceStatus
from app.models.risk import AllocationStatus, RiskLevel

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_text_preview_collapses_whitespace(self):
        assert _text_preview("a\n  b\t c") == "a b c"

    def test_text_preview_truncates(self):
        assert len(_text_preview("x" * 500)) == 160

    def test_text_preview_empty(self):
        assert _text_preview(None) is None
        assert _text_preview("   ") is None

    def test_unmet_demand_empty_list_is_not_unmet(self):
        assert _has_unmet_demand([]) is False
        assert _has_unmet_demand(None) is False
        assert _has_unmet_demand({}) is False

    def test_unmet_demand_present(self):
        assert _has_unmet_demand([{"resource_type": "ambulance"}]) is True
        assert _has_unmet_demand({"ambulance": 2}) is True


# ---------------------------------------------------------------------------
# Overview payload assembly
# ---------------------------------------------------------------------------

class TestOverviewPayload:
    def test_empty_data_is_all_zeros_not_fabricated(self):
        overview = build_overview_payload({"counts": {}, "with_unmet_demand": 0})
        assert overview.incident_metrics.total == 0
        assert overview.incident_metrics.critical_risk == 0
        assert overview.event_metrics.awaiting_analysis == 0
        assert overview.resource_metrics.available == 0
        assert overview.optimization_metrics.pending_approvals == 0
        assert overview.recent_incidents == []
        assert overview.recent_events == []
        assert overview.pending_approvals == []
        assert overview.generated_at is not None

    def test_awaiting_analysis_derived_from_totals(self):
        overview = build_overview_payload(
            {"counts": {"events_total": 100, "events_analyzed": 70}}
        )
        assert overview.event_metrics.awaiting_analysis == 30

    def test_awaiting_analysis_never_negative(self):
        overview = build_overview_payload(
            {"counts": {"events_total": 5, "events_analyzed": 8}}
        )
        assert overview.event_metrics.awaiting_analysis == 0

    def test_counts_map_to_metrics(self):
        counts = {
            "incidents_total": 12,
            "incidents_active": 7,
            "incidents_critical": 2,
            "incidents_high": 3,
            "resources_total": 9,
            "resources_available": 4,
            "pending_approvals": 5,
        }
        overview = build_overview_payload({"counts": counts, "with_unmet_demand": 3})
        assert overview.incident_metrics.total == 12
        assert overview.incident_metrics.active == 7
        assert overview.incident_metrics.critical_risk == 2
        assert overview.incident_metrics.high_risk == 3
        assert overview.incident_metrics.with_unmet_demand == 3
        assert overview.resource_metrics.available == 4
        assert overview.optimization_metrics.pending_approvals == 5

    def test_items_are_parsed(self):
        inc_id = uuid4()
        overview = build_overview_payload(
            {
                "counts": {"incidents_total": 1},
                "recent_incidents": [
                    {
                        "id": inc_id,
                        "title": "Flood",
                        "status": "active",
                        "event_count": 2,
                        "risk_level": "high",
                        "risk_score": 74.0,
                    }
                ],
            }
        )
        assert len(overview.recent_incidents) == 1
        assert overview.recent_incidents[0].title == "Flood"
        assert overview.recent_incidents[0].risk_level == "high"

    def test_incident_summary_payload_shape(self):
        payload = build_incidents_summary_payload(
            [
                {
                    "id": uuid4(),
                    "title": "Quake",
                    "status": "active",
                    "event_count": 1,
                }
            ],
            total=1,
            limit=20,
            offset=0,
        )
        assert payload.total == 1
        assert payload.limit == 20
        assert payload.incidents[0].title == "Quake"


# ---------------------------------------------------------------------------
# gather_overview against a stub session
# ---------------------------------------------------------------------------

class _Result:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar(self):
        return self._scalar

    def all(self):
        return self._rows

    def scalars(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None


class _StubSession:
    """Returns canned results in the exact order ``gather_overview`` asks."""

    def __init__(self, results):
        self._results = list(results)
        self._i = 0

    async def execute(self, *_args, **_kwargs):
        result = self._results[self._i]
        self._i += 1
        return result


def _inc(title, status=IncidentStatus.ACTIVE, events=2):
    return SimpleNamespace(
        id=uuid4(),
        title=title,
        incident_type="flood",
        summary=None,
        status=status,
        event_count=events,
        confidence=0.8,
        centroid_latitude=12.9,
        centroid_longitude=77.6,
        start_time=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc),
    )


def _stub_results_sequence():
    inc1, inc2 = _inc("Incident A"), _inc("Incident B", events=5)
    risk1 = SimpleNamespace(
        incident_id=inc1.id,
        risk_score=85.0,
        risk_level=RiskLevel.CRITICAL,
        assessed_at=datetime.now(timezone.utc),
    )
    risk2 = SimpleNamespace(
        incident_id=inc2.id,
        risk_score=50.0,
        risk_level=RiskLevel.ELEVATED,
        assessed_at=datetime.now(timezone.utc),
    )
    inv1 = SimpleNamespace(
        incident_id=inc1.id,
        assessment="moderately_supported",
        evidence_confidence=0.7,
        investigated_at=datetime.now(timezone.utc),
    )
    opt_met = SimpleNamespace(
        incident_id=inc1.id,
        unmet_demand=[],
        created_at=datetime.now(timezone.utc),
    )
    opt_unmet = SimpleNamespace(
        incident_id=inc2.id,
        unmet_demand=[{"resource_type": "ambulance"}],
        created_at=datetime.now(timezone.utc),
    )
    ev1 = SimpleNamespace(
        id=uuid4(), source="social_media", event_type="flood",
        text_content="Water rising fast", location_name="MG Road",
        latitude=12.9, longitude=77.6, timestamp=datetime.now(timezone.utc),
    )
    ev2 = SimpleNamespace(
        id=uuid4(), source="news", event_type="flood",
        text_content="Roads submerged", location_name="Ring Road",
        latitude=12.91, longitude=77.61, timestamp=datetime.now(timezone.utc),
    )
    alloc1 = SimpleNamespace(
        id=uuid4(), incident_id=inc1.id, resource_id=uuid4(),
        resource_type="ambulance", distance_meters=1200.0,
        assignment_reason="closest", created_at=datetime.now(timezone.utc),
        status=AllocationStatus.RECOMMENDED,
    )
    alloc2 = SimpleNamespace(
        id=uuid4(), incident_id=inc2.id, resource_id=uuid4(),
        resource_type="fire_vehicle", distance_meters=800.0,
        assignment_reason="nearest", created_at=datetime.now(timezone.utc),
        status=AllocationStatus.RECOMMENDED,
    )
    title_rows = [
        SimpleNamespace(id=inc1.id, title=inc1.title),
        SimpleNamespace(id=inc2.id, title=inc2.title),
    ]
    name_rows = [
        SimpleNamespace(id=alloc1.resource_id, name="Ambulance 1"),
        SimpleNamespace(id=alloc2.resource_id, name="Fire Truck 2"),
    ]
    return [
        _Result(scalar=10),   # incidents_total
        _Result(scalar=6),    # active+emerging
        _Result(scalar=2),    # emerging
        _Result(scalar=1),    # resolved
        _Result(scalar=4),    # recent 24h
        _Result(scalar=3),    # critical
        _Result(scalar=2),    # high
        _Result(scalar=100),  # events_total
        _Result(scalar=40),   # events_recent_24h
        _Result(scalar=70),   # events_analyzed
        _Result(rows=[(ResourceStatus.AVAILABLE, 5), (ResourceStatus.DEPLOYED, 2), (ResourceStatus.UNKNOWN, 1)]),
        _Result(scalar=4),    # incidents_with_optimization
        _Result(scalar=2),    # pending_approvals
        _Result(scalar=3),    # approved_allocations
        _Result(rows=[opt_unmet, opt_met]),  # latest-per-incident unmet
        _Result(rows=[inc1, inc2]),          # recent incidents
        _Result(rows=[risk1, risk2]),        # risk assessments
        _Result(rows=[inv1]),                # investigations
        _Result(rows=[ev1, ev2]),            # recent events
        _Result(rows=[SimpleNamespace(event_id=ev1.id, disaster_type="flood")]),
        _Result(rows=[alloc1, alloc2]),      # pending allocations
        _Result(rows=title_rows),            # incident titles
        _Result(rows=name_rows),             # resource names
    ]


class TestGatherOverview:
    async def test_populated(self):
        session = _StubSession(_stub_results_sequence())
        data = await gather_overview(session, limit_recent=10)
        overview = build_overview_payload(data)

        assert overview.incident_metrics.total == 10
        assert overview.incident_metrics.active == 6
        assert overview.incident_metrics.critical_risk == 3
        assert overview.incident_metrics.high_risk == 2
        assert overview.event_metrics.total == 100
        assert overview.event_metrics.analyzed == 70
        assert overview.event_metrics.awaiting_analysis == 30
        assert overview.resource_metrics.total == 8
        assert overview.resource_metrics.available == 5
        assert overview.resource_metrics.deployed == 2
        assert overview.resource_metrics.unknown == 1
        assert overview.optimization_metrics.pending_approvals == 2
        # inc1 latest run met demand; inc2 still unmet -> exactly 1
        assert overview.incident_metrics.with_unmet_demand == 1

        a = next(i for i in overview.recent_incidents if i.title == "Incident A")
        assert a.risk_level == "critical"
        assert a.risk_score == 85.0
        assert a.evidence_assessment == "moderately_supported"

        first_event = overview.recent_events[0]
        assert first_event.analysis_status == "completed"  # ev1 has analysis
        assert overview.recent_events[1].analysis_status == "pending"

        approval = overview.pending_approvals[0]
        assert approval.incident_title in {"Incident A", "Incident B"}
        assert approval.resource_name in {"Ambulance 1", "Fire Truck 2"}

    async def test_empty_database(self):
        # Empty DB: every count scalar is 0 and IN-queries return no rows.
        results = [_Result(scalar=0) for _ in range(15)]
        results.append(_Result(rows=[]))   # unmet
        results.append(_Result(rows=[]))   # recent incidents
        results.append(_Result(rows=[]))   # recent events
        results.append(_Result(rows=[]))   # pending allocations
        session = _StubSession(results)
        overview = build_overview_payload(await gather_overview(session, limit_recent=10))
        assert overview.incident_metrics.total == 0
        assert overview.incident_metrics.with_unmet_demand == 0
        assert overview.recent_incidents == []
        assert overview.recent_events == []
        assert overview.pending_approvals == []


# ---------------------------------------------------------------------------
# Route validation (runs before any DB access)
# ---------------------------------------------------------------------------

class TestEndpointValidation:
    async def test_overview_limit_bounds(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/dashboard/overview", params={"limit_recent": 0})
            assert resp.status_code == 422

    async def test_summary_invalid_status(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/dashboard/incidents/summary", params={"status": "bogus"}
            )
            assert resp.status_code == 422

    async def test_summary_invalid_risk_level(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/dashboard/incidents/summary", params={"risk_level": "bogus"}
            )
            assert resp.status_code == 422

    async def test_summary_invalid_sort(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/dashboard/incidents/summary", params={"sort_by": "bogus"}
            )
            assert resp.status_code == 422

    async def test_dashboard_routes_registered(self):
        schema = app.openapi()
        assert "/api/v1/dashboard/overview" in schema["paths"]
        assert "/api/v1/dashboard/incidents/summary" in schema["paths"]
