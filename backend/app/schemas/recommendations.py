"""
Pydantic schemas for the Commercial Recommendation Engine.

All enums and models used by:
    - RecommendationService (service layer)
    - GET /hotels/{id}/recommendations (API layer)
    - Frontend (serialised JSON)
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────


class RecommendationCategory(str, Enum):
    pricing = "pricing"
    inventory = "inventory"
    restrictions = "restrictions"
    upgrade = "upgrade"
    package = "package"
    ancillary = "ancillary"
    operational = "operational"


class RecommendationAction(str, Enum):
    # Pricing
    increase_rate = "increase_rate"
    reduce_rate = "reduce_rate"
    hold_rate = "hold_rate"
    # Inventory
    protect_premium_inventory = "protect_premium_inventory"
    release_premium_inventory = "release_premium_inventory"
    hold_rooms_for_late_demand = "hold_rooms_for_late_demand"
    # Restrictions
    close_discounted_rates = "close_discounted_rates"
    add_minimum_length_of_stay = "add_minimum_length_of_stay"
    remove_minimum_length_of_stay = "remove_minimum_length_of_stay"
    # Upgrade
    open_paid_upgrades = "open_paid_upgrades"
    restrict_complimentary_upgrades = "restrict_complimentary_upgrades"
    # Package / ancillary
    launch_breakfast_package = "launch_breakfast_package"
    launch_parking_package = "launch_parking_package"
    launch_event_package = "launch_event_package"
    promote_late_checkout = "promote_late_checkout"
    # Operational
    alert_revenue_manager = "alert_revenue_manager"
    alert_front_desk = "alert_front_desk"
    alert_housekeeping = "alert_housekeeping"


class RecommendationPriority(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class RecommendationConfidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class RecommendationStatus(str, Enum):
    proposed = "proposed"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"


class ReasonCode(str, Enum):
    high_forecast_occupancy = "high_forecast_occupancy"
    very_high_forecast_occupancy = "very_high_forecast_occupancy"
    low_forecast_occupancy = "low_forecast_occupancy"
    event_demand = "event_demand"
    competitor_rate_support = "competitor_rate_support"
    competitor_rate_below = "competitor_rate_below"
    high_booking_pace = "high_booking_pace"
    low_booking_pace = "low_booking_pace"
    premium_inventory_scarce = "premium_inventory_scarce"
    operational_pressure = "operational_pressure"
    multi_night_demand_peak = "multi_night_demand_peak"
    high_cancellation_risk = "high_cancellation_risk"
    value_add_opportunity = "value_add_opportunity"


# ── Per-recommendation model ──────────────────────────────────────────────────


class Recommendation(BaseModel):
    """A single ranked commercial recommendation."""

    id: str = Field(..., description="Stable deterministic ID: REC-{hotel}-{date}-{category}-{seq}")
    hotel_id: str
    category: RecommendationCategory
    action: RecommendationAction
    title: str
    summary: str

    effective_start_date: date
    effective_end_date: date

    # Numeric context
    current_value: float | None = Field(None, description="Current rate / count (unit-dependent)")
    recommended_value: float | None = Field(None, description="Recommended rate / count")
    unit: str = Field("USD", description="Unit label, e.g. USD, rooms, nights")

    # Ranking signals
    score: float = Field(..., description="Composite score used for ranking (higher = more urgent)")
    priority: RecommendationPriority
    confidence: RecommendationConfidence

    # Impact estimates (labelled as estimates – not causal claims)
    expected_revenue_impact: float = Field(
        0.0, description="Estimated revenue impact (USD). Label as estimate."
    )
    expected_occupancy_impact: float = Field(
        0.0, description="Estimated occupancy % change. May be 0 for rate-only actions."
    )

    # Transparency
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    supporting_factors: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)

    status: RecommendationStatus = RecommendationStatus.proposed
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Response envelope ─────────────────────────────────────────────────────────


class RecommendationSummary(BaseModel):
    total: int
    critical: int
    high: int
    medium: int
    low: int
    estimated_revenue_opportunity: float


class RecommendationResponse(BaseModel):
    """Full response envelope for GET /hotels/{id}/recommendations."""

    model_config = {"protected_namespaces": ()}

    hotel_id: str
    generated_at: datetime
    forecast_model: str
    adjustment_model: str
    recommendation_model: str
    summary: RecommendationSummary
    recommendations: list[Recommendation]


# ── Market signals (input to the engine) ─────────────────────────────────────


class MarketSignals(BaseModel):
    """
    Mock market signals consumed by the recommendation engine.

    Behind an interface so a real market-data feed can replace this
    without touching the rule logic (see services/market_signals/).
    """

    competitor_adr: float = Field(..., description="Compset average daily rate (USD)")
    competitor_occupancy: float = Field(..., description="Compset occupancy % (0–100)")
    booking_pace_index: float = Field(
        ..., description="Pace vs. same period last year (1.0 = normal, >1.0 = ahead)"
    )
    cancellation_rate: float = Field(..., description="Current cancellation rate % (0–100)")
    premium_rooms_available: int = Field(..., description="Number of available premium/suite rooms")
    expected_arrivals: int = Field(..., description="Expected check-ins for the first forecast date")
