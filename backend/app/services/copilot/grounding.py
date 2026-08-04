"""
Grounding helpers — build structured context objects that get passed to the LLM.

These functions consume the existing schema types produced by the deterministic
engines and convert them into the flat CopilotGrounding models that the LLM
service uses to compose prompts.

Design principle
────────────────
The grounding layer is the contract between the deterministic engines and the
LLM.  It ensures:
  - The LLM only ever sees facts that the deterministic engines have already
    validated and produced.
  - No raw user input or PII enters the prompt.
  - The existing ExplainabilityPanel's outputs are never duplicated here —
    only *downstream* commercial/ancillary actions reference event facts.
"""
from __future__ import annotations

from app.schemas.ancillaries import AncillaryRecommendation, AncillaryRecommendationResponse
from app.schemas.copilot import (
    AncillaryGrounding,
    CommercialGrounding,
    ExecutiveSummaryGrounding,
)
from app.schemas.recommendations import Recommendation, RecommendationResponse


def commercial_grounding(
    hotel_name: str,
    rec: Recommendation,
    rec_response: RecommendationResponse,
    current_adr: float,
    competitor_adr: float,
    booking_pace_index: float,
    active_events: list[dict],
) -> CommercialGrounding:
    """
    Build a CommercialGrounding from one Recommendation + its response context.
    Called by the /copilot/explain-commercial endpoint.
    """
    return CommercialGrounding(
        hotel_name=hotel_name,
        as_of_date=rec.effective_start_date.isoformat(),
        current_occupancy_pct=0.0,          # filled by endpoint from metrics
        forecast_occupancy_pct=0.0,         # filled by endpoint
        current_adr=current_adr,
        competitor_adr=competitor_adr,
        booking_pace_index=booking_pace_index,
        active_events=active_events,
        recommendation_title=rec.title,
        recommendation_action=rec.action.value,
        recommendation_category=rec.category.value,
        current_value=rec.current_value,
        recommended_value=rec.recommended_value,
        unit=rec.unit,
        expected_revenue_impact=rec.expected_revenue_impact,
        reason_codes=[rc.value for rc in rec.reason_codes],
        supporting_factors=rec.supporting_factors,
        risk_flags=rec.risk_flags,
        priority=rec.priority.value,
        confidence=rec.confidence.value,
    )


def ancillary_grounding(
    hotel_name: str,
    rec: AncillaryRecommendation,
    persona: str,
    forecast_occupancy: float,
    active_events: list[dict],
) -> AncillaryGrounding:
    """
    Build an AncillaryGrounding from one AncillaryRecommendation.
    """
    sc = rec.score_components
    components: dict = {}
    if sc:
        components = {
            "propensity": sc.propensity_score,
            "margin": sc.margin_score,
            "demand": sc.demand_relevance_score,
            "segment": sc.segment_affinity_score,
            "event": sc.event_relevance_score,
            "capacity": sc.capacity_score,
        }
    return AncillaryGrounding(
        hotel_name=hotel_name,
        persona=persona,
        forecast_occupancy_pct=forecast_occupancy,
        active_events=active_events,
        ancillary_name=rec.product.name,
        ancillary_category=rec.product.category.value,
        rank=rec.rank,
        base_price=rec.base_price,
        recommended_price=rec.recommended_price,
        price_change_pct=rec.price_change_pct,
        purchase_probability=rec.propensity,
        expected_revenue=rec.expected_revenue,
        expected_margin=rec.expected_margin,
        opportunity_score=rec.score,
        reason_codes=rec.reason_codes,
        supporting_factors=rec.supporting_factors,
        guardrails_applied=[],      # no guardrails_applied field on schema yet
        score_components=components,
    )


def executive_summary_grounding(
    hotel_name: str,
    as_of_date: str,
    current_occupancy: float,
    forecast_occupancy: float,
    current_adr: float,
    competitor_adr: float,
    active_events: list[dict],
    rec_response: RecommendationResponse,
    anc_response: AncillaryRecommendationResponse,
    persona: str,
) -> ExecutiveSummaryGrounding:
    """
    Build an ExecutiveSummaryGrounding from both engine outputs.
    """
    forecast_uplift = forecast_occupancy - current_occupancy

    top_commercial = [r.title for r in rec_response.recommendations[:3]]
    top_ancillary = [
        f"{r.product.name} (#{r.rank}, ${r.recommended_price:.0f})"
        for r in anc_response.recommendations[:3]
    ]

    return ExecutiveSummaryGrounding(
        hotel_name=hotel_name,
        as_of_date=as_of_date,
        current_occupancy_pct=current_occupancy,
        forecast_occupancy_pct=forecast_occupancy,
        forecast_uplift_pct=round(forecast_uplift, 1),
        current_adr=current_adr,
        competitor_adr=competitor_adr,
        active_events=active_events,
        room_revenue_opportunity=rec_response.summary.estimated_revenue_opportunity,
        ancillary_revenue_opportunity=anc_response.summary.total_revenue_opportunity,
        total_revenue_opportunity=(
            rec_response.summary.estimated_revenue_opportunity
            + anc_response.summary.total_revenue_opportunity
        ),
        top_commercial_actions=top_commercial,
        top_ancillary_offers=top_ancillary,
        persona=persona,
    )
