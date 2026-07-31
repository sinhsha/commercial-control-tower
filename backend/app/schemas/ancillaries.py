"""
Pydantic schemas for the Ancillary Revenue Optimization Engine.

All enums and models used by:
    - AncillaryRecommendationService (service layer)
    - GET /hotels/{id}/ancillaries (API layer)
    - GET /hotels/{id}/ancillary-recommendations (API layer)
    - Frontend (serialised JSON)
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────


class AncillaryCategory(str, Enum):
    parking_transportation = "parking_transportation"
    food_beverage = "food_beverage"
    meetings_events = "meetings_events"
    spa_wellness = "spa_wellness"
    experiences = "experiences"
    workspace = "workspace"
    guest_commerce = "guest_commerce"
    pet = "pet"
    room_inventory = "room_inventory"


class RevenueImpactTier(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class SuppressionReason(str, Enum):
    NO_CAPACITY = "NO_CAPACITY"
    SEGMENT_NOT_RELEVANT = "SEGMENT_NOT_RELEVANT"
    BELOW_PROPENSITY_THRESHOLD = "BELOW_PROPENSITY_THRESHOLD"
    MARGIN_TOO_LOW = "MARGIN_TOO_LOW"
    INVENTORY_CONSTRAINED = "INVENTORY_CONSTRAINED"
    HOTEL_OCCUPANCY_TOO_HIGH = "HOTEL_OCCUPANCY_TOO_HIGH"
    EVENT_NOT_RELEVANT = "EVENT_NOT_RELEVANT"
    PRODUCT_INACTIVE = "PRODUCT_INACTIVE"
    GUEST_NOT_ELIGIBLE = "GUEST_NOT_ELIGIBLE"


class GuestPersona(str, Enum):
    hotel_wide = "hotel_wide"
    business_traveler = "business_traveler"
    conference_attendee = "conference_attendee"
    leisure_couple = "leisure_couple"
    family = "family"
    resort_guest = "resort_guest"
    ev_traveler = "ev_traveler"
    pet_traveler = "pet_traveler"


# ── Product model ─────────────────────────────────────────────────────────────


class AncillaryProduct(BaseModel):
    """A single ancillary product in the catalog."""

    model_config = {"protected_namespaces": ()}

    code: str = Field(..., description="Stable unique product code (e.g. PARKING)")
    name: str
    description: str
    category: AncillaryCategory
    base_price: float = Field(..., description="List price in USD")
    variable_cost: float = Field(..., description="Marginal cost per unit in USD")
    daily_capacity: int = Field(..., description="Max units available per day")
    current_utilization: float = Field(
        ..., ge=0.0, le=1.0, description="Current fill rate (0–1)"
    )
    revenue_impact_tier: RevenueImpactTier
    is_active: bool = True

    # Eligibility flags
    requires_vehicle_flag: bool = False
    requires_ev_flag: bool = False
    requires_pet_flag: bool = False

    # Targeting
    target_segments: list[GuestPersona] = Field(
        default_factory=list,
        description="Personas for which this offer is most relevant. Empty = hotel-wide.",
    )
    applicable_event_types: list[str] = Field(
        default_factory=list,
        description="Event types that boost relevance (e.g. convention, sports).",
    )

    # Propensity base rate (fraction of guests who convert absent other signals)
    base_propensity: float = Field(
        0.20, ge=0.0, le=1.0, description="Baseline conversion rate (0–1)"
    )


# ── Context model ─────────────────────────────────────────────────────────────


class AncillaryContext(BaseModel):
    """
    All inputs needed by the ancillary engine for one hotel/persona/horizon window.
    Built from real DB data (metrics, events, market signals) by the service layer.
    NOT supplied by the API caller.
    """

    model_config = {"protected_namespaces": ()}

    hotel_id: str
    as_of: date
    horizon_days: int = 14
    total_rooms: int

    # Current demand signals
    current_occupancy: float = Field(..., description="Current occupancy % (0–100)")
    forecast_occupancy: float = Field(
        ..., description="Avg forecast occupancy over horizon (0–100)"
    )
    demand_level: float = Field(..., ge=0.0, le=100.0, description="Demand index 0–100")

    # Active events
    active_event_types: list[str] = Field(default_factory=list)
    has_active_event: bool = False

    # Guest profile (shaped by persona)
    persona: GuestPersona = GuestPersona.hotel_wide
    estimated_eligible_guests: int = Field(
        100, description="Estimated daily eligible guests for this persona"
    )
    avg_stay_length: float = Field(1.8, description="Average stay length in nights")

    # Guest flags
    vehicle_flag: bool = False  # True when parking / vehicle offers are relevant
    ev_vehicle_flag: bool = False  # True for EV charging
    pet_flag: bool = False  # True for pet programs


# ── Score components ──────────────────────────────────────────────────────────


class AncillaryScoreComponents(BaseModel):
    """Transparency breakdown of the composite score."""

    propensity_score: float = Field(..., description="Contribution from propensity (0–30)")
    margin_score: float = Field(..., description="Contribution from margin (0–25)")
    demand_relevance_score: float = Field(
        ..., description="Contribution from demand level (0–20)"
    )
    segment_affinity_score: float = Field(
        ..., description="Contribution from segment alignment (0–15)"
    )
    event_relevance_score: float = Field(
        ..., description="Contribution from active events (0–7)"
    )
    capacity_score: float = Field(
        ..., description="Contribution from available capacity (0–3)"
    )
    total: float = Field(..., description="Sum of component scores (0–100)")


# ── Recommendation model ──────────────────────────────────────────────────────


class AncillaryRecommendation(BaseModel):
    """A single ranked ancillary recommendation."""

    model_config = {"protected_namespaces": ()}

    id: str = Field(
        ..., description="Stable deterministic ID: ANC-{hotel}-{date}-{code}-{rank}"
    )
    hotel_id: str
    rank: int = Field(..., description="1-based rank within this response")

    product: AncillaryProduct
    persona: GuestPersona

    # Pricing
    base_price: float
    recommended_price: float
    price_change_pct: float = Field(
        0.0, description="% change from base price (positive = increase)"
    )
    price_change_reason: str = ""

    # Propensity
    propensity: float = Field(..., ge=0.0, le=1.0, description="Estimated conversion rate")

    # Expected value (labelled as estimates)
    eligible_guests: int
    expected_conversions: float
    expected_revenue: float = Field(
        ..., description="Estimated revenue. Label as estimate."
    )
    expected_margin: float = Field(
        ..., description="Estimated margin. Label as estimate."
    )

    # Composite score
    score: float = Field(..., description="Composite score 0–100 (higher = better offer)")
    score_components: AncillaryScoreComponents

    # Confidence (aligned with RecommendationConfidence naming)
    confidence: str = Field("medium", description="high / medium / low")

    # Transparency
    reason_codes: list[str] = Field(default_factory=list)
    supporting_factors: list[str] = Field(default_factory=list)

    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Response envelopes ────────────────────────────────────────────────────────


class AncillaryRecommendationSummary(BaseModel):
    eligible_products: int
    shown: int
    total_revenue_opportunity: float = Field(
        ..., description="Sum of expected_revenue across shown offers. Estimate."
    )
    total_margin_opportunity: float = Field(
        ..., description="Sum of expected_margin across shown offers. Estimate."
    )


class AncillaryRecommendationResponse(BaseModel):
    """Full response envelope for GET /hotels/{id}/ancillary-recommendations."""

    model_config = {"protected_namespaces": ()}

    hotel_id: str
    generated_at: datetime
    engine_model: str
    persona: GuestPersona
    horizon_days: int
    summary: AncillaryRecommendationSummary
    recommendations: list[AncillaryRecommendation]


class AncillaryCatalogResponse(BaseModel):
    """Full catalog response for GET /hotels/{id}/ancillaries."""

    hotel_id: str
    total: int
    items: list[AncillaryProduct]
