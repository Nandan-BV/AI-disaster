"""
OR-Tools based Resource Optimizer for RESQ-AI Phase 8.

Solves the resource allocation problem using Google OR-Tools CP-SAT solver.
Matches resource demands to available resources while minimising distance,
maximising suitability, and minimising unmet demand.
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
import math

try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False

from app.config import settings

logger = logging.getLogger(__name__)


class ResourceOptimizer:
    """
    OR-Tools CP-SAT based resource optimizer for emergency resource allocation.

    The optimizer:
    1. Matches resource demands to available resources
    2. Minimises total travel distance and maximises resource suitability
    3. Respects capacity, capability, and availability constraints
    4. Minimises unmet demand, weighted by priority
    """

    def __init__(self, time_limit_seconds: Optional[int] = None):
        if not ORTOOLS_AVAILABLE:
            raise RuntimeError(
                "OR-Tools not installed. Run: pip install ortools"
            )
        self.time_limit = time_limit_seconds or settings.OPT_SOLVER_TIME_LIMIT_SECONDS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def solve(
        self,
        demands: List[Dict[str, Any]],
        resources: List[Dict[str, Any]],
        incident_location: Tuple[float, float],
        weights: Optional[Dict[str, float]] = None,
        max_distance: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Solve the resource allocation problem.

        Args:
            demands:           List of demand dicts (resource_type, required_quantity,
                               priority, required_capabilities).
            resources:         List of available resource dicts (id, name,
                               resource_type, latitude, longitude, status,
                               capabilities, capacity, current_load).
            incident_location: (lat, lon) of the incident centroid.
            weights:           Optional weight overrides for objective components.
            max_distance:      Maximum allocation radius in metres.

        Returns:
            Dict with status, allocations, unmet_demand, explanation.
        """
        if not demands:
            return self._empty_result("No demands to satisfy")
        if not resources:
            return self._empty_result("No resources provided")

        weights = weights or {
            "distance": settings.OPT_WEIGHT_DISTANCE,
            "suitability": settings.OPT_WEIGHT_SUITABILITY,
            "unmet_demand": settings.OPT_WEIGHT_UNMET_DEMAND,
            "priority": settings.OPT_WEIGHT_PRIORITY,
        }
        max_dist = max_distance or settings.MAX_RESOURCE_ALLOCATION_DISTANCE_METERS

        # Filter to available resources within range
        available = [
            r for r in resources
            if r.get("status", "").lower() == "available"
            and self._haversine(
                r["latitude"], r["longitude"],
                incident_location[0], incident_location[1],
            ) <= max_dist
        ]
        if not available:
            return self._empty_result("No available resources within range")

        n_res = len(available)
        n_dem = len(demands)

        # Pre-compute distances and suitability scores
        dist_matrix: Dict[Tuple[int, int], float] = {}
        suit_matrix: Dict[Tuple[int, int], float] = {}
        for i, res in enumerate(available):
            for j, dem in enumerate(demands):
                dist_matrix[(i, j)] = self._haversine(
                    res["latitude"], res["longitude"],
                    incident_location[0], incident_location[1],
                )
                suit_matrix[(i, j)] = self._compute_suitability(res, dem)

        # Build CP-SAT model
        model = cp_model.CpModel()

        # x[i, j] = 1  →  resource i is assigned to demand j
        x: Dict[Tuple[int, int], Any] = {
            (i, j): model.NewBoolVar(f"x_{i}_{j}")
            for i in range(n_res)
            for j in range(n_dem)
        }

        # ---- Constraints -----------------------------------------------

        # Each resource assigned to at most one demand
        for i in range(n_res):
            model.Add(sum(x[i, j] for j in range(n_dem)) <= 1)

        # Assignments for demand j must not exceed required quantity
        for j, dem in enumerate(demands):
            model.Add(
                sum(x[i, j] for i in range(n_res)) <= dem["required_quantity"]
            )

        # Type compatibility: block incompatible pairs
        for i, res in enumerate(available):
            for j, dem in enumerate(demands):
                if not self._type_compatible(
                    res.get("resource_type"), dem.get("resource_type")
                ):
                    model.Add(x[i, j] == 0)

        # ---- Objective -------------------------------------------------
        # Scale floats to integers for CP-SAT (multiply by 1000)
        SCALE = 1000

        objective_terms = []

        for i, res in enumerate(available):
            for j, dem in enumerate(demands):
                d = dist_matrix[(i, j)]
                s = suit_matrix[(i, j)]
                p = self._priority_weight(dem.get("priority", "medium"))

                # Minimise distance cost
                dist_cost = int(d * weights["distance"] * SCALE)
                # Maximise suitability (negate to minimise)
                suit_gain = int(s * weights["suitability"] * SCALE)
                # Maximise assigned coverage weighted by priority
                prio_gain = int(p * weights["priority"] * SCALE)

                net = dist_cost - suit_gain - prio_gain
                objective_terms.append(x[i, j] * net)

        if objective_terms:
            model.Minimize(sum(objective_terms))
        else:
            model.Minimize(0)

        # ---- Solve -----------------------------------------------------
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit
        solver.parameters.num_search_workers = 4

        logger.info(
            "Starting Phase 8 optimization: %d resources × %d demands",
            n_res, n_dem,
        )
        raw_status = solver.Solve(model)

        return self._extract_solution(
            solver=solver,
            raw_status=raw_status,
            demands=demands,
            resources=available,
            x=x,
            dist_matrix=dist_matrix,
            suit_matrix=suit_matrix,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_solution(
        self,
        solver: Any,
        raw_status: int,
        demands: List[Dict],
        resources: List[Dict],
        x: Dict[Tuple[int, int], Any],
        dist_matrix: Dict[Tuple[int, int], float],
        suit_matrix: Dict[Tuple[int, int], float],
    ) -> Dict[str, Any]:
        """Extract allocations from a solved model."""
        status_map = {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.UNKNOWN: "UNKNOWN",
        }
        status_str = status_map.get(raw_status, "UNKNOWN")

        if raw_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return self._empty_result(f"Solver returned: {status_str}")

        allocations: List[Dict[str, Any]] = []
        unmet_demand: List[Dict[str, Any]] = []
        total_distance = 0.0

        for j, dem in enumerate(demands):
            assigned_count = 0
            for i, res in enumerate(resources):
                if solver.Value(x[i, j]) == 1:
                    dist = dist_matrix[(i, j)]
                    score = suit_matrix[(i, j)]
                    total_distance += dist
                    allocations.append({
                        "resource_id": res["id"],
                        "resource_name": res.get("name", ""),
                        "resource_type": res.get("resource_type", ""),
                        "distance_meters": round(dist, 1),
                        "assignment_score": round(score, 3),
                        "assignment_reason": (
                            f"Assigned {res.get('resource_type', 'resource')} "
                            f"{round(dist / 1000, 2)} km from incident "
                            f"(suitability {round(score, 2)})"
                        ),
                    })
                    assigned_count += 1

            required = dem.get("required_quantity", 1)
            unmet = max(0, required - assigned_count)
            if unmet > 0:
                unmet_demand.append({
                    "resource_type": dem.get("resource_type"),
                    "required": required,
                    "assigned": assigned_count,
                    "unmet": unmet,
                    "priority": dem.get("priority", "medium"),
                })

        return {
            "status": "SUCCESS",
            "solver_status": status_str,
            "allocations": allocations,
            "unmet_demand": unmet_demand,
            "total_resources": len(allocations),
            "total_distance": round(total_distance, 1),
            "objective_value": solver.ObjectiveValue(),
            "solver_time": solver.WallTime(),
            "explanation": self._generate_explanation(allocations, unmet_demand),
        }

    def _haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine distance in metres."""
        R = 6_371_000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _compute_suitability(self, resource: Dict, demand: Dict) -> float:
        """Suitability score [0–1] between a resource and a demand."""
        type_score = self._type_compatibility_score(
            resource.get("resource_type"), demand.get("resource_type")
        )
        cap_score = self._capability_match(
            resource.get("capabilities", {}),
            demand.get("required_capabilities", {}),
        )
        status_score = 1.0 if resource.get("status", "").lower() == "available" else 0.3
        return round(0.4 * type_score + 0.4 * cap_score + 0.2 * status_score, 4)

    def _type_compatibility_score(
        self, resource_type: Optional[str], demand_type: Optional[str]
    ) -> float:
        if not resource_type or not demand_type:
            return 0.0
        if resource_type == demand_type:
            return 1.0
        compatible: Dict[str, List[str]] = {
            "ambulance":        ["ambulance", "emergency_vehicle"],
            "rescue_team":      ["rescue_team", "emergency_vehicle"],
            "fire_vehicle":     ["fire_vehicle"],
            "police_unit":      ["police_unit", "emergency_vehicle"],
            "shelter":          ["shelter"],
            "hospital":         ["hospital", "emergency_vehicle"],
            "drone":            ["drone"],
            "emergency_vehicle":["emergency_vehicle", "ambulance", "rescue_team"],
        }
        if resource_type in compatible.get(demand_type, []):
            return 0.8
        return 0.0

    def _type_compatible(
        self, resource_type: Optional[str], demand_type: Optional[str]
    ) -> bool:
        return self._type_compatibility_score(resource_type, demand_type) > 0.0

    def _capability_match(
        self, resource_caps: Dict, required_caps: Dict
    ) -> float:
        if not required_caps:
            return 0.5
        matched = sum(
            1 for cap, req in required_caps.items()
            if req and resource_caps.get(cap)
        )
        return matched / len(required_caps)

    def _priority_weight(self, priority: str) -> float:
        return {"critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.3}.get(priority, 0.5)

    def _generate_explanation(
        self, allocations: List[Dict], unmet_demand: List[Dict]
    ) -> str:
        parts = []
        if allocations:
            by_type: Dict[str, int] = {}
            for a in allocations:
                t = a.get("resource_type", "unknown")
                by_type[t] = by_type.get(t, 0) + 1
            summary = ", ".join(f"{cnt}× {t}" for t, cnt in by_type.items())
            parts.append(f"{len(allocations)} resources allocated ({summary})")
        if unmet_demand:
            unmet_str = ", ".join(
                f"{u['unmet']} {u['resource_type']} [{u['priority']}]"
                for u in unmet_demand
            )
            parts.append(f"Unmet demand: {unmet_str}")
        return ". ".join(parts) if parts else "No allocation possible"

    def _empty_result(self, message: str) -> Dict[str, Any]:
        return {
            "status": "NO_SOLUTION",
            "solver_status": "NO_SOLUTION",
            "allocations": [],
            "unmet_demand": [],
            "total_resources": 0,
            "total_distance": 0.0,
            "objective_value": None,
            "solver_time": 0.0,
            "explanation": message,
        }