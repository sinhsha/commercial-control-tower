"""
Pydantic schemas for the Copilot / Grounded Explanation Service.

These models cover the four surfaces where LLM-generated text is used:
  1. Commercial recommendation explanation
  2. Ancillary recommendation explanation
  3. Total revenue executive summary
  4. Revenue Manager Copilot (free-form Q&A, synthesis)

IMPORTANT CONSTRAINT
────────────────────
The existing ExplainabilityPanel (demand-event/adjusted-forecast rationale)
is a fully deterministic component and must NOT be replaced, duplicated,
or overwritten by this service.

The LLM MAY reference structured event facts as grounding when explaining
a downstream commercial or ancillary action, but it must not regenerate
the event rationale itself.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────────


class CopilotSurface(str, Enum):
    """Which surface the LLM explanation is generated for."""
    commercial_recommendation = "commercial_recommendation"
    ancillary_recommendation  = "ancillary_recommendation"
    executive_summary         = "executive_summary"
    copilot_question          = "copilot_question"


class CopilotStatus(str, Enum):
    ok          = "ok"
    unavailable = "unavailable"   # LLM not configured / API key missing
    error       = "error"         # LLM call failed


# ── Grounding payload (structured data sent to LLM) ───────────────────────────


class CommercialGrounding(BaseModel):
    """Structured facts from the commercial recommendation engine."""
    hotel_name: str
    as_of_date: str
    current_occupancy_pct: float
    forecast_occupancy_pct: float
    current_adr: float
    competitor_adr: float
    booking_pace_index: float
    active_events: list[dict[str, Any]] = Field(default_factory=list,
        description="List of {name, event_type, attendance, distance_miles}")
    recommendation_title: str
    recommendation_action: str
    recommendation_category: str
    current_value: float | None
    recommended_value: float | None
    unit: str
    expected_revenue_impact: float
    reason_codes: list[str]
    supporting_factors: list[str]
    risk_flags: list[str]
    priority: str
    confidence: str


class AncillaryGrounding(BaseModel):
    """Structured facts from the ancillary recommendation engine."""
    hotel_name: str
    persona: str
    forecast_occupancy_pct: float
    active_events: list[dict[str, Any]] = Field(default_factory=list)
    ancillary_name: str
    ancillary_category: str
    rank: int
    base_price: float
    recommended_price: float
    price_change_pct: float
    purchase_probability: float
    expected_revenue: float
    expected_margin: float
    opportunity_score: float
    reason_codes: list[str]
    supporting_factors: list[str]
    guardrails_applied: list[str]
    score_components: dict[str, float]


class ExecutiveSummaryGrounding(BaseModel):
    """Structured facts for the total-revenue executive summary."""
    hotel_name: str
    as_of_date: str
    current_occupancy_pct: float
    forecast_occupancy_pct: float
    forecast_uplift_pct: float
    current_adr: float
    competitor_adr: float
    active_events: list[dict[str, Any]] = Field(default_factory=list)
    room_revenue_opportunity: float
    ancillary_revenue_opportunity: float
    total_revenue_opportunity: float
    top_commercial_actions: list[str]
    top_ancillary_offers: list[str]
    persona: str


class CopilotQuestion(BaseModel):
    """A free-form revenue manager question with full structured context."""
    question: str = Field(..., min_length=3, max_length=500)
    hotel_name: str
    as_of_date: str
    current_occupancy_pct: float
    forecast_occupancy_pct: float
    current_adr: float
    competitor_adr: float
    active_events: list[dict[str, Any]] = Field(default_factory=list)
    top_commercial_actions: list[str] = Field(default_factory=list)
    top_ancillary_offers: list[str] = Field(default_factory=list)
    room_revenue_opportunity: float = 0.0
    ancillary_revenue_opportunity: float = 0.0
    persona: str = "hotel_wide"


# ── Request / Response models ─────────────────────────────────────────────────


class ExplainCommercialRequest(BaseModel):
    grounding: CommercialGrounding


class ExplainAncillaryRequest(BaseModel):
    grounding: AncillaryGrounding


class ExplainExecutiveSummaryRequest(BaseModel):
    grounding: ExecutiveSummaryGrounding


class CopilotAskRequest(BaseModel):
    grounding: CopilotQuestion


class CopilotResponse(BaseModel):
    """Standard response envelope for all copilot endpoints."""
    surface: CopilotSurface
    status: CopilotStatus
    explanation: str = Field(
        "", description="LLM-generated explanation. Empty when status != ok."
    )
    model_used: str = ""
    tokens_used: int = 0
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fallback_reason: str | None = None
