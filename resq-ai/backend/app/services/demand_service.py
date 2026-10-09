from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.incident import Incident, IncidentEvent
from app.models.event import Event
from app.models.event_analysis import EventAIAnalysis
from app.models.risk import (
    RiskAssessment, ImpactAssessment,
    ResourceDemand, DemandPriority,
    EnvironmentalConditions,
)


class DemandEstimationService:
    """Service for estimating resource demands based on incident characteristics."""

    # Base demand rules by incident type
    BASE_DEMANDS: Dict[str, List[Dict[str, Any]]] = {
        "flood": [
            {"resource_type": "ambulance",       "base_qty": 2, "priority": "high",   "reason": "Medical evacuations and rescue"},
            {"resource_type": "rescue_team",      "base_qty": 1, "priority": "high",   "reason": "Water rescue operations"},
            {"resource_type": "shelter",          "base_qty": 1, "priority": "medium", "reason": "Temporary housing for displaced"},
            {"resource_type": "emergency_vehicle","base_qty": 1, "priority": "medium", "reason": "Command and control"},
        ],
        "wildfire": [
            {"resource_type": "fire_vehicle",     "base_qty": 3, "priority": "critical","reason": "Fire suppression"},
            {"resource_type": "ambulance",        "base_qty": 2, "priority": "high",    "reason": "Burn injuries and smoke inhalation"},
            {"resource_type": "rescue_team",      "base_qty": 1, "priority": "high",    "reason": "Search and rescue"},
            {"resource_type": "emergency_vehicle","base_qty": 1, "priority": "medium",  "reason": "Command post"},
        ],
        "earthquake": [
            {"resource_type": "rescue_team",      "base_qty": 3, "priority": "critical","reason": "Urban search and rescue"},
            {"resource_type": "ambulance",        "base_qty": 3, "priority": "critical","reason": "Mass casualty medical"},
            {"resource_type": "emergency_vehicle","base_qty": 2, "priority": "high",    "reason": "Command and coordination"},
            {"resource_type": "shelter",          "base_qty": 2, "priority": "high",    "reason": "Mass displacement"},
        ],
        "landslide": [
            {"resource_type": "rescue_team",      "base_qty": 2, "priority": "critical","reason": "Technical rope rescue"},
            {"resource_type": "ambulance",        "base_qty": 2, "priority": "high",    "reason": "Trauma care"},
            {"resource_type": "emergency_vehicle","base_qty": 1, "priority": "medium",  "reason": "Access road clearance"},
        ],
        "cyclone": [
            {"resource_type": "shelter",          "base_qty": 2, "priority": "critical","reason": "Mass evacuation housing"},
            {"resource_type": "ambulance",        "base_qty": 2, "priority": "high",    "reason": "Storm injuries"},
            {"resource_type": "emergency_vehicle","base_qty": 1, "priority": "high",    "reason": "Evacuation coordination"},
            {"resource_type": "fire_vehicle",     "base_qty": 1, "priority": "medium",  "reason": "Structural fires"},
        ],
        "building_collapse": [
            {"resource_type": "rescue_team",      "base_qty": 3, "priority": "critical","reason": "Structural collapse rescue"},
            {"resource_type": "ambulance",        "base_qty": 3, "priority": "critical","reason": "Crush injuries"},
            {"resource_type": "fire_vehicle",     "base_qty": 1, "priority": "high",    "reason": "Fire risk"},
        ],
    }

    # Risk level multipliers
    RISK_MULTIPLIERS = {
        "low": 0.5,
        "moderate": 1.0,
        "elevated": 1.5,
        "high": 2.0,
        "critical": 3.0,
    }

    # Minimum capability requirements per resource type
    CAPABILITIES = {
        "ambulance":        {"medical": True, "trauma": True},
        "rescue_team":      {"heavy_rescue": True, "rope_rescue": True},
        "fire_vehicle":     {"fire_suppression": True, "water_supply": True},
        "police_unit":      {"traffic_control": True, "crowd_management": True},
        "shelter":          {"capacity": 50, "sanitation": True},
        "hospital":         {"emergency": True, "trauma_center": True, "icu": True},
        "drone":            {"aerial_surveillance": True, "thermal_imaging": True},
        "emergency_vehicle":{"communications": True, "command_control": True},
    }

    async def estimate_demands(
        self,
        incident_id: str,
        db: AsyncSession,
        incident_type: Optional[str] = None,
        risk_assessment: Optional[Any] = None,
        impact_assessment: Optional[Any] = None,
        env_conditions: Optional[Any] = None,
        ai_analysis: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Estimate resource demands for an incident.

        Uses incident type, risk level, population exposure, and infrastructure
        exposure to scale base demand quantities. Falls back gracefully when
        optional context objects are None.
        """
        # Resolve incident type
        itype = (incident_type or "unknown").lower()
        base_demands = self.BASE_DEMANDS.get(itype, [])

        if not base_demands:
            # Generic fallback for unknown disaster types
            base_demands = [
                {"resource_type": "ambulance",        "base_qty": 1, "priority": "medium", "reason": "General medical support"},
                {"resource_type": "emergency_vehicle","base_qty": 1, "priority": "medium", "reason": "Command and control"},
            ]

        # --- risk level multiplier ---
        multiplier = 1.0
        if risk_assessment is not None:
            rl = risk_assessment.risk_level
            rl_str = rl.value if hasattr(rl, "value") else str(rl)
            multiplier = self.RISK_MULTIPLIERS.get(rl_str, 1.0)

        # --- population exposure multiplier ---
        pop_multiplier = 1.0
        if impact_assessment is not None:
            pop = getattr(impact_assessment, "population_potentially_exposed", None)
            if pop:
                if pop > 10000:
                    pop_multiplier = 2.0
                elif pop > 5000:
                    pop_multiplier = 1.5
                elif pop > 1000:
                    pop_multiplier = 1.2

        # --- infrastructure exposure multiplier ---
        infra_multiplier = 1.0
        if impact_assessment is not None:
            infra = getattr(impact_assessment, "infrastructure_potentially_exposed", None)
            if infra:
                if infra > 10:
                    infra_multiplier = 1.5
                elif infra > 5:
                    infra_multiplier = 1.2

        total_multiplier = multiplier * pop_multiplier * infra_multiplier

        # Build demand list
        estimated: List[Dict[str, Any]] = []
        for base in base_demands:
            qty = max(1, round(base["base_qty"] * total_multiplier))
            estimated.append({
                "resource_type": base["resource_type"],
                "required_quantity": qty,
                "priority": base["priority"],
                "reason": base["reason"],
                "minimum_capability": self.CAPABILITIES.get(base["resource_type"], {}),
            })

        # Deduplicate — keep highest-priority entry per resource type
        by_type: Dict[str, Dict[str, Any]] = {}
        for d in estimated:
            rt = d["resource_type"]
            if rt not in by_type or self._priority_value(d["priority"]) > self._priority_value(by_type[rt]["priority"]):
                by_type[rt] = d

        return list(by_type.values())

    # ------------------------------------------------------------------
    def _priority_value(self, priority: str) -> int:
        return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(priority, 0)