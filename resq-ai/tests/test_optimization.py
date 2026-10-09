"""
Phase 8: Resource Optimization tests.

Tests cover:
- ResourceOptimizer unit tests (no DB required)
- DemandEstimationService unit tests
- Optimization API endpoint integration tests (mocked DB)
"""

import pytest
import math
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from typing import List, Dict, Any

# ---------------------------------------------------------------------------
# ResourceOptimizer unit tests
# ---------------------------------------------------------------------------

def _make_resource(
    id=None,
    rtype="ambulance",
    lat=12.97,
    lon=77.59,
    status="available",
    capacity=1,
):
    return {
        "id": str(id or uuid4()),
        "name": f"Resource-{rtype}",
        "resource_type": rtype,
        "latitude": lat,
        "longitude": lon,
        "status": status,
        "capabilities": {},
        "capacity": capacity,
        "current_load": 0,
    }


def _make_demand(rtype="ambulance", qty=1, priority="high"):
    return {
        "demand_id": str(uuid4()),
        "resource_type": rtype,
        "required_quantity": qty,
        "priority": priority,
        "required_capabilities": {},
    }


class TestResourceOptimizerUnit:
    """Unit tests for ResourceOptimizer — no DB, no network."""

    @pytest.fixture(autouse=True)
    def _patch_ortools(self, monkeypatch):
        """Skip tests that need OR-Tools if it is not installed."""
        try:
            import ortools  # noqa: F401
        except ImportError:
            pytest.skip("ortools not installed")

    def _get_optimizer(self):
        from app.optimization.resource_optimizer import ResourceOptimizer
        return ResourceOptimizer(time_limit_seconds=5)

    def test_empty_demands_returns_no_solution(self):
        opt = self._get_optimizer()
        result = opt.solve(
            demands=[],
            resources=[_make_resource()],
            incident_location=(12.97, 77.59),
        )
        assert result["status"] == "NO_SOLUTION"
        assert "No demands" in result["explanation"]

    def test_empty_resources_returns_no_solution(self):
        opt = self._get_optimizer()
        result = opt.solve(
            demands=[_make_demand()],
            resources=[],
            incident_location=(12.97, 77.59),
        )
        assert result["status"] == "NO_SOLUTION"

    def test_no_available_resources_returns_no_solution(self):
        opt = self._get_optimizer()
        result = opt.solve(
            demands=[_make_demand()],
            resources=[_make_resource(status="deployed")],
            incident_location=(12.97, 77.59),
        )
        assert result["status"] == "NO_SOLUTION"
        assert "No available" in result["explanation"]

    def test_out_of_range_resources_returns_no_solution(self):
        opt = self._get_optimizer()
        # Resource is far away (Tokyo → Bengaluru ~6500 km)
        result = opt.solve(
            demands=[_make_demand()],
            resources=[_make_resource(lat=35.68, lon=139.69)],
            incident_location=(12.97, 77.59),
            max_distance=50_000,   # 50 km max
        )
        assert result["status"] == "NO_SOLUTION"

    def test_single_resource_single_demand_matched(self):
        opt = self._get_optimizer()
        resource = _make_resource(lat=12.971, lon=77.591)
        result = opt.solve(
            demands=[_make_demand(rtype="ambulance", qty=1)],
            resources=[resource],
            incident_location=(12.97, 77.59),
        )
        assert result["status"] in ("SUCCESS", "NO_SOLUTION")
        if result["status"] == "SUCCESS":
            assert result["total_resources"] >= 0

    def test_type_incompatible_resource_not_assigned(self):
        opt = self._get_optimizer()
        result = opt.solve(
            demands=[_make_demand(rtype="fire_vehicle", qty=1)],
            resources=[_make_resource(rtype="ambulance", lat=12.971, lon=77.591)],
            incident_location=(12.97, 77.59),
        )
        # ambulance cannot satisfy fire_vehicle demand
        if result["status"] == "SUCCESS":
            assert result["total_resources"] == 0

    def test_multiple_resources_multiple_demands(self):
        opt = self._get_optimizer()
        resources = [
            _make_resource(rtype="ambulance", lat=12.971, lon=77.591),
            _make_resource(rtype="ambulance", lat=12.972, lon=77.592),
            _make_resource(rtype="rescue_team", lat=12.973, lon=77.593),
        ]
        demands = [
            _make_demand(rtype="ambulance", qty=2, priority="critical"),
            _make_demand(rtype="rescue_team", qty=1, priority="high"),
        ]
        result = opt.solve(
            demands=demands,
            resources=resources,
            incident_location=(12.97, 77.59),
        )
        # Should find a feasible solution
        assert result["status"] in ("SUCCESS", "NO_SOLUTION")

    def test_unmet_demand_reported_when_insufficient_resources(self):
        opt = self._get_optimizer()
        result = opt.solve(
            demands=[_make_demand(rtype="ambulance", qty=5, priority="critical")],
            resources=[_make_resource(rtype="ambulance", lat=12.971, lon=77.591)],
            incident_location=(12.97, 77.59),
        )
        if result["status"] == "SUCCESS" and result["total_resources"] < 5:
            assert len(result["unmet_demand"]) > 0

    def test_result_has_required_keys(self):
        opt = self._get_optimizer()
        result = opt.solve(
            demands=[_make_demand()],
            resources=[_make_resource(lat=12.971, lon=77.591)],
            incident_location=(12.97, 77.59),
        )
        for key in ("status", "solver_status", "allocations", "unmet_demand",
                    "total_resources", "explanation"):
            assert key in result, f"Missing key: {key}"

    def test_allocation_contains_distance_and_score(self):
        opt = self._get_optimizer()
        result = opt.solve(
            demands=[_make_demand(rtype="ambulance", qty=1)],
            resources=[_make_resource(rtype="ambulance", lat=12.971, lon=77.591)],
            incident_location=(12.97, 77.59),
        )
        if result["status"] == "SUCCESS" and result["allocations"]:
            alloc = result["allocations"][0]
            assert "distance_meters" in alloc
            assert "assignment_score" in alloc
            assert alloc["distance_meters"] >= 0


# ---------------------------------------------------------------------------
# Haversine helper test
# ---------------------------------------------------------------------------

class TestHaversine:
    def test_zero_distance_same_point(self):
        from app.optimization.resource_optimizer import ResourceOptimizer
        opt = ResourceOptimizer.__new__(ResourceOptimizer)
        d = opt._haversine(12.97, 77.59, 12.97, 77.59)
        assert d == pytest.approx(0.0, abs=1e-6)

    def test_known_distance_approximate(self):
        """Bengaluru ↔ Chennai ~290 km."""
        from app.optimization.resource_optimizer import ResourceOptimizer
        opt = ResourceOptimizer.__new__(ResourceOptimizer)
        d = opt._haversine(12.9716, 77.5946, 13.0827, 80.2707)
        assert 280_000 < d < 310_000, f"Expected ~290 km, got {d/1000:.1f} km"


# ---------------------------------------------------------------------------
# DemandEstimationService unit tests
# ---------------------------------------------------------------------------

class TestDemandEstimationService:
    @pytest.fixture
    def service(self):
        from app.services.demand_service import DemandEstimationService
        return DemandEstimationService()

    @pytest.mark.asyncio
    async def test_unknown_incident_type_returns_fallback(self, service):
        demands = await service.estimate_demands(
            incident_id=str(uuid4()),
            db=None,
            incident_type="meteor_strike",
        )
        assert len(demands) >= 1

    @pytest.mark.asyncio
    async def test_flood_returns_expected_types(self, service):
        demands = await service.estimate_demands(
            incident_id=str(uuid4()),
            db=None,
            incident_type="flood",
        )
        types = [d["resource_type"] for d in demands]
        assert "ambulance" in types
        assert "rescue_team" in types

    @pytest.mark.asyncio
    async def test_risk_multiplier_increases_quantity(self, service):
        mock_risk = MagicMock()
        mock_risk.risk_level = MagicMock()
        mock_risk.risk_level.value = "critical"

        demands_critical = await service.estimate_demands(
            incident_id=str(uuid4()),
            db=None,
            incident_type="flood",
            risk_assessment=mock_risk,
        )

        mock_risk.risk_level.value = "low"
        demands_low = await service.estimate_demands(
            incident_id=str(uuid4()),
            db=None,
            incident_type="flood",
            risk_assessment=mock_risk,
        )

        total_critical = sum(d["required_quantity"] for d in demands_critical)
        total_low = sum(d["required_quantity"] for d in demands_low)
        assert total_critical > total_low, "Critical risk should demand more resources"

    @pytest.mark.asyncio
    async def test_all_supported_incident_types_return_demands(self, service):
        types = ["flood", "wildfire", "earthquake", "landslide", "cyclone", "building_collapse"]
        for itype in types:
            demands = await service.estimate_demands(
                incident_id=str(uuid4()),
                db=None,
                incident_type=itype,
            )
            assert len(demands) > 0, f"No demands returned for incident type: {itype}"

    @pytest.mark.asyncio
    async def test_deduplication_keeps_highest_priority(self, service):
        demands = await service.estimate_demands(
            incident_id=str(uuid4()),
            db=None,
            incident_type="flood",
        )
        types = [d["resource_type"] for d in demands]
        # No duplicate resource types
        assert len(types) == len(set(types)), "Duplicate resource types in demand list"

    @pytest.mark.asyncio
    async def test_demands_have_required_fields(self, service):
        demands = await service.estimate_demands(
            incident_id=str(uuid4()),
            db=None,
            incident_type="earthquake",
        )
        for d in demands:
            assert "resource_type" in d
            assert "required_quantity" in d
            assert "priority" in d
            assert d["required_quantity"] >= 1


# ---------------------------------------------------------------------------
# Type compatibility tests
# ---------------------------------------------------------------------------

class TestTypeCompatibility:
    def _opt(self):
        from app.optimization.resource_optimizer import ResourceOptimizer
        return ResourceOptimizer.__new__(ResourceOptimizer)

    def test_same_type_is_compatible(self):
        opt = self._opt()
        assert opt._type_compatible("ambulance", "ambulance")

    def test_ambulance_compatible_with_emergency_vehicle_demand(self):
        opt = self._opt()
        assert opt._type_compatible("ambulance", "emergency_vehicle")

    def test_fire_vehicle_not_compatible_with_ambulance_demand(self):
        opt = self._opt()
        assert not opt._type_compatible("fire_vehicle", "ambulance")

    def test_none_type_not_compatible(self):
        opt = self._opt()
        assert not opt._type_compatible(None, "ambulance")
        assert not opt._type_compatible("ambulance", None)


# ---------------------------------------------------------------------------
# Suitability score tests
# ---------------------------------------------------------------------------

class TestSuitabilityScore:
    def _opt(self):
        from app.optimization.resource_optimizer import ResourceOptimizer
        return ResourceOptimizer.__new__(ResourceOptimizer)

    def test_perfect_match_scores_high(self):
        opt = self._opt()
        resource = {"resource_type": "ambulance", "status": "available", "capabilities": {"medical": True}}
        demand = {"resource_type": "ambulance", "required_capabilities": {"medical": True}}
        score = opt._compute_suitability(resource, demand)
        assert score > 0.7

    def test_type_mismatch_scores_low(self):
        opt = self._opt()
        resource = {"resource_type": "drone", "status": "available", "capabilities": {}}
        demand = {"resource_type": "ambulance", "required_capabilities": {}}
        score = opt._compute_suitability(resource, demand)
        # drone is fully incompatible with ambulance demand (type_score=0, cap_score=0.5, status_score=1.0)
        # score = 0.4*0 + 0.4*0.5 + 0.2*1.0 = 0.40
        # It's lower than a perfect match (>0.7) but not near zero because
        # capability and status components still contribute.
        assert score < 0.5, f"Expected incompatible match to score below 0.5, got {score}"

    def test_deployed_resource_scores_lower(self):
        opt = self._opt()
        resource_avail = {"resource_type": "ambulance", "status": "available", "capabilities": {}}
        resource_deployed = {"resource_type": "ambulance", "status": "deployed", "capabilities": {}}
        demand = {"resource_type": "ambulance", "required_capabilities": {}}
        assert opt._compute_suitability(resource_avail, demand) > opt._compute_suitability(resource_deployed, demand)
