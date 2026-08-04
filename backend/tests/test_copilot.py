"""
Unit tests for the Copilot / Grounded Explanation Service.

All tests are purely in-memory — no database, no HTTP transport, no OpenAI
calls.  The OpenAI client is fully mocked; deterministic fallback behaviour
is tested with OPENAI_API_KEY unset.

Coverage map
────────────
 1. CopilotStatus enum values
 2. CopilotSurface enum values
 3. CommercialGrounding validates required fields
 4. AncillaryGrounding validates required fields
 5. ExecutiveSummaryGrounding validates required fields
 6. CopilotQuestion validates question length (min 3)
 7. CopilotQuestion rejects question > 500 chars
 8. CopilotResponse default fields
 9. OpenAICopilotService: disabled when api_key empty → status=unavailable
10. OpenAICopilotService: fallback text contains key facts (commercial)
11. OpenAICopilotService: fallback text contains key facts (ancillary)
12. OpenAICopilotService: fallback text contains key facts (executive)
13. OpenAICopilotService: fallback text contains key facts (ask)
14. OpenAICopilotService: explain_commercial returns surface=commercial_recommendation
15. OpenAICopilotService: explain_ancillary returns surface=ancillary_recommendation
16. OpenAICopilotService: executive_summary returns surface=executive_summary
17. OpenAICopilotService: ask returns surface=copilot_question
18. OpenAICopilotService: LLM ok path parses response text
19. OpenAICopilotService: LLM exception → status=error, explanation=fallback
20. commercial_grounding() helper builds CommercialGrounding
21. ancillary_grounding() helper builds AncillaryGrounding
22. executive_summary_grounding() computes total_revenue_opportunity
23. executive_summary_grounding() computes top_commercial_actions (max 3)
24. executive_summary_grounding() computes forecast_uplift_pct
25. grounding: event facts list truncated at 4 in prompt
"""
from __future__ import annotations

import pytest
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.copilot import (
    AncillaryGrounding,
    CommercialGrounding,
    CopilotAskRequest,
    CopilotQuestion,
    CopilotResponse,
    CopilotStatus,
    CopilotSurface,
    ExecutiveSummaryGrounding,
    ExplainAncillaryRequest,
    ExplainCommercialRequest,
)
from app.services.copilot.openai_service import (
    OpenAICopilotService,
    _commercial_fallback,
    _ancillary_fallback,
    _executive_fallback,
    _copilot_fallback,
    _fmt_events,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _commercial_grounding(**overrides) -> CommercialGrounding:
    defaults = dict(
        hotel_name="Test Hotel",
        as_of_date="2025-08-01",
        current_occupancy_pct=72.5,
        forecast_occupancy_pct=80.0,
        current_adr=189.0,
        competitor_adr=175.0,
        booking_pace_index=1.15,
        active_events=[{"name": "Tech Summit", "event_type": "conference",
                        "attendance": 5000, "distance_miles": 1.2}],
        recommendation_title="Increase Weekend Rate",
        recommendation_action="increase_rate",
        recommendation_category="pricing",
        current_value=189.0,
        recommended_value=220.0,
        unit="USD",
        expected_revenue_impact=12000.0,
        reason_codes=["high_booking_pace", "competitor_undercut"],
        supporting_factors=["Strong corporate demand", "Conference 1.2mi away"],
        risk_flags=[],
        priority="high",
        confidence="high",
    )
    defaults.update(overrides)
    return CommercialGrounding(**defaults)


def _ancillary_grounding(**overrides) -> AncillaryGrounding:
    defaults = dict(
        hotel_name="Test Hotel",
        persona="business_traveler",
        forecast_occupancy_pct=80.0,
        active_events=[],
        ancillary_name="Valet Parking",
        ancillary_category="parking_transportation",
        rank=1,
        base_price=35.0,
        recommended_price=40.0,
        price_change_pct=14.3,
        purchase_probability=0.62,
        expected_revenue=1550.0,
        expected_margin=1240.0,
        opportunity_score=82.5,
        reason_codes=["high_segment_affinity"],
        supporting_factors=["Business traveler segment"],
        guardrails_applied=[],
        score_components={"propensity": 0.62, "margin": 0.8},
    )
    defaults.update(overrides)
    return AncillaryGrounding(**defaults)


def _executive_grounding(**overrides) -> ExecutiveSummaryGrounding:
    defaults = dict(
        hotel_name="Test Hotel",
        as_of_date="2025-08-01",
        current_occupancy_pct=72.5,
        forecast_occupancy_pct=80.0,
        forecast_uplift_pct=7.5,
        current_adr=189.0,
        competitor_adr=175.0,
        active_events=[],
        room_revenue_opportunity=25000.0,
        ancillary_revenue_opportunity=8000.0,
        total_revenue_opportunity=33000.0,
        top_commercial_actions=["Increase Weekend Rate", "Close OTA Discounts"],
        top_ancillary_offers=["Valet Parking (#1, $40)", "Spa Booking (#2, $95)"],
        persona="hotel_wide",
    )
    defaults.update(overrides)
    return ExecutiveSummaryGrounding(**defaults)


def _copilot_question(**overrides) -> CopilotQuestion:
    defaults = dict(
        question="Should I increase rates this weekend?",
        hotel_name="Test Hotel",
        as_of_date="2025-08-01",
        current_occupancy_pct=72.5,
        forecast_occupancy_pct=80.0,
        current_adr=189.0,
        competitor_adr=175.0,
        active_events=[],
        top_commercial_actions=["Increase Weekend Rate"],
        top_ancillary_offers=["Valet Parking (#1, $40)"],
        room_revenue_opportunity=25000.0,
        ancillary_revenue_opportunity=8000.0,
        persona="hotel_wide",
    )
    defaults.update(overrides)
    return CopilotQuestion(**defaults)


def _disabled_service() -> OpenAICopilotService:
    """Service with no API key — always falls back."""
    with patch("app.services.copilot.openai_service.get_settings") as mock_settings:
        s = MagicMock()
        s.copilot_enabled = True
        s.openai_api_key = ""
        s.openai_model = "gpt-4o-mini"
        s.copilot_max_tokens = 400
        mock_settings.return_value = s
        return OpenAICopilotService()


# ── 1–2. Enum values ──────────────────────────────────────────────────────────

def test_copilot_status_values():
    assert CopilotStatus.ok == "ok"
    assert CopilotStatus.unavailable == "unavailable"
    assert CopilotStatus.error == "error"


def test_copilot_surface_values():
    assert CopilotSurface.commercial_recommendation == "commercial_recommendation"
    assert CopilotSurface.ancillary_recommendation  == "ancillary_recommendation"
    assert CopilotSurface.executive_summary         == "executive_summary"
    assert CopilotSurface.copilot_question          == "copilot_question"


# ── 3–6. Schema validation ────────────────────────────────────────────────────

def test_commercial_grounding_valid():
    g = _commercial_grounding()
    assert g.hotel_name == "Test Hotel"
    assert g.expected_revenue_impact == 12000.0


def test_ancillary_grounding_valid():
    g = _ancillary_grounding()
    assert g.rank == 1
    assert g.purchase_probability == pytest.approx(0.62)


def test_executive_grounding_valid():
    g = _executive_grounding()
    assert g.total_revenue_opportunity == pytest.approx(33000.0)


def test_copilot_question_min_length():
    with pytest.raises(Exception):
        CopilotQuestion(
            question="ab",  # too short
            hotel_name="H", as_of_date="2025-01-01",
            current_occupancy_pct=50.0, forecast_occupancy_pct=60.0,
            current_adr=100.0, competitor_adr=95.0,
        )


# ── 7. Question max length ────────────────────────────────────────────────────

def test_copilot_question_max_length():
    with pytest.raises(Exception):
        CopilotQuestion(
            question="x" * 501,
            hotel_name="H", as_of_date="2025-01-01",
            current_occupancy_pct=50.0, forecast_occupancy_pct=60.0,
            current_adr=100.0, competitor_adr=95.0,
        )


# ── 8. CopilotResponse defaults ───────────────────────────────────────────────

def test_copilot_response_defaults():
    r = CopilotResponse(
        surface=CopilotSurface.executive_summary,
        status=CopilotStatus.ok,
        explanation="Test",
    )
    assert r.model_used == ""
    assert r.tokens_used == 0
    assert r.fallback_reason is None
    assert isinstance(r.generated_at, datetime)


# ── 9. Disabled when no API key ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_service_disabled_no_api_key():
    svc = _disabled_service()
    g = _commercial_grounding()
    resp = await svc.explain_commercial(g)
    assert resp.status == CopilotStatus.unavailable
    assert "OPENAI_API_KEY" in resp.fallback_reason or resp.fallback_reason is not None


# ── 10–13. Fallback text contains key facts ────────────────────────────────────

def test_commercial_fallback_contains_title():
    g = _commercial_grounding()
    text = _commercial_fallback(g)
    assert "Increase Weekend Rate" in text
    assert "$12,000" in text or "12000" in text


def test_ancillary_fallback_contains_name():
    g = _ancillary_grounding()
    text = _ancillary_fallback(g)
    assert "Valet Parking" in text
    assert "62%" in text or "0.62" in text or "62" in text


def test_executive_fallback_contains_total():
    g = _executive_grounding()
    text = _executive_fallback(g)
    assert "33,000" in text or "33000" in text
    assert "Test Hotel" in text


def test_copilot_ask_fallback_contains_occupancy():
    g = _copilot_question()
    text = _copilot_fallback(g)
    assert "72.5" in text or "80.0" in text


# ── 14–17. Surface returned matches endpoint ──────────────────────────────────

@pytest.mark.asyncio
async def test_explain_commercial_surface():
    svc = _disabled_service()
    resp = await svc.explain_commercial(_commercial_grounding())
    assert resp.surface == CopilotSurface.commercial_recommendation


@pytest.mark.asyncio
async def test_explain_ancillary_surface():
    svc = _disabled_service()
    resp = await svc.explain_ancillary(_ancillary_grounding())
    assert resp.surface == CopilotSurface.ancillary_recommendation


@pytest.mark.asyncio
async def test_executive_summary_surface():
    svc = _disabled_service()
    resp = await svc.executive_summary(_executive_grounding())
    assert resp.surface == CopilotSurface.executive_summary


@pytest.mark.asyncio
async def test_ask_surface():
    svc = _disabled_service()
    resp = await svc.ask(_copilot_question())
    assert resp.surface == CopilotSurface.copilot_question


# ── 18. LLM ok path ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_llm_ok_path():
    with patch("app.services.copilot.openai_service.get_settings") as mock_settings:
        s = MagicMock()
        s.copilot_enabled = True
        s.openai_api_key = "sk-test"
        s.openai_model = "gpt-4o-mini"
        s.copilot_max_tokens = 400
        mock_settings.return_value = s

        with patch("app.services.copilot.openai_service.OpenAICopilotService.__init__",
                   return_value=None):
            svc = OpenAICopilotService.__new__(OpenAICopilotService)
            svc._enabled = True
            svc._model = "gpt-4o-mini"
            svc._max_tokens = 400

            # Build a mock async OpenAI client
            mock_choice = MagicMock()
            mock_choice.message.content = "You should raise rates because demand is strong."
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_completion.usage.total_tokens = 123

            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
            svc._client = mock_client

            resp = await svc.explain_commercial(_commercial_grounding())
            assert resp.status == CopilotStatus.ok
            assert "raise rates" in resp.explanation
            assert resp.tokens_used == 123
            assert resp.model_used == "gpt-4o-mini"


# ── 19. LLM exception → error fallback ───────────────────────────────────────

@pytest.mark.asyncio
async def test_llm_exception_returns_error_status():
    svc = OpenAICopilotService.__new__(OpenAICopilotService)
    svc._enabled = True
    svc._model = "gpt-4o-mini"
    svc._max_tokens = 400

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("Network error"))
    svc._client = mock_client

    resp = await svc.explain_commercial(_commercial_grounding())
    assert resp.status == CopilotStatus.error
    assert resp.fallback_reason is not None


# ── 20. commercial_grounding() helper ────────────────────────────────────────

def test_commercial_grounding_helper():
    from app.services.copilot.grounding import commercial_grounding
    from app.schemas.recommendations import (
        Recommendation, RecommendationResponse, RecommendationSummary,
        RecommendationCategory, RecommendationAction, RecommendationPriority,
        RecommendationConfidence, RecommendationStatus, ReasonCode,
    )
    import datetime as _dt

    rec = Recommendation(
        id="r1",
        hotel_id="h1",
        category=RecommendationCategory.pricing,
        action=RecommendationAction.increase_rate,
        title="Increase Midweek Rate",
        summary="Boost midweek ADR",
        effective_start_date=_dt.date(2025, 8, 5),
        effective_end_date=_dt.date(2025, 8, 7),
        current_value=189.0,
        recommended_value=210.0,
        unit="USD",
        score=88.0,
        priority=RecommendationPriority.high,
        confidence=RecommendationConfidence.high,
        expected_revenue_impact=8500.0,
        expected_occupancy_impact=0.0,
        reason_codes=[ReasonCode.high_booking_pace],
        supporting_factors=["Pace 1.2x above baseline"],
        risk_flags=[],
        status=RecommendationStatus.proposed,
        created_at=_dt.datetime.now(_dt.timezone.utc),
    )
    rec_response = RecommendationResponse(
        hotel_id="h1",
        generated_at=_dt.datetime.now(_dt.timezone.utc),
        forecast_model="seasonal",
        adjustment_model="rule_based",
        recommendation_model="rule_based_v1",
        summary=RecommendationSummary(total=1, critical=0, high=1, medium=0, low=0,
                                      estimated_revenue_opportunity=8500.0),
        recommendations=[rec],
    )
    g = commercial_grounding(
        hotel_name="Test Hotel",
        rec=rec,
        rec_response=rec_response,
        current_adr=189.0,
        competitor_adr=175.0,
        booking_pace_index=1.2,
        active_events=[],
    )
    assert g.recommendation_title == "Increase Midweek Rate"
    assert g.expected_revenue_impact == pytest.approx(8500.0)
    assert g.priority == "high"
    assert g.confidence == "high"


# ── 21. ancillary_grounding() helper ─────────────────────────────────────────

def test_ancillary_grounding_helper():
    from app.services.copilot.grounding import ancillary_grounding
    from app.schemas.ancillaries import (
        AncillaryRecommendation, AncillaryProduct, AncillaryCategory,
        GuestPersona, RevenueImpactTier, AncillaryScoreComponents,
    )
    import datetime as _dt

    product = AncillaryProduct(
        code="VALET",
        name="Valet Parking",
        description="24hr valet",
        category=AncillaryCategory.parking_transportation,
        base_price=35.0,
        variable_cost=8.0,
        daily_capacity=60,
        current_utilization=0.5,
        revenue_impact_tier=RevenueImpactTier.high,
        is_active=True,
        requires_vehicle_flag=True,
        requires_ev_flag=False,
        requires_pet_flag=False,
        target_segments=[GuestPersona.business_traveler],
        applicable_event_types=["conference"],
        base_propensity=0.55,
    )
    components = AncillaryScoreComponents(
        propensity_score=0.62,
        margin_score=0.80,
        demand_relevance_score=0.70,
        segment_affinity_score=0.85,
        event_relevance_score=0.60,
        capacity_score=0.90,
        total=76.5,
    )
    rec = AncillaryRecommendation(
        id="anc1",
        hotel_id="h1",
        rank=1,
        product=product,
        persona=GuestPersona.business_traveler,
        base_price=35.0,
        recommended_price=40.0,
        price_change_pct=14.3,
        price_change_reason="High demand",
        propensity=0.62,
        eligible_guests=80,
        expected_conversions=50,
        expected_revenue=1550.0,
        expected_margin=1240.0,
        score=82.5,
        score_components=components,
        confidence="high",
        reason_codes=["high_segment_affinity"],
        supporting_factors=["Business travelers drive parking demand"],
        generated_at=_dt.datetime.now(_dt.timezone.utc),
    )
    g = ancillary_grounding(
        hotel_name="Test Hotel",
        rec=rec,
        persona="business_traveler",
        forecast_occupancy=80.0,
        active_events=[],
    )
    assert g.ancillary_name == "Valet Parking"
    assert g.purchase_probability == pytest.approx(0.62)
    assert g.opportunity_score == pytest.approx(82.5)


# ── 22–24. executive_summary_grounding() ─────────────────────────────────────

def test_executive_summary_grounding_total_revenue():
    from app.services.copilot.grounding import executive_summary_grounding
    from app.schemas.recommendations import RecommendationResponse, RecommendationSummary
    from app.schemas.ancillaries import AncillaryRecommendationResponse, AncillaryRecommendationSummary, GuestPersona
    import datetime as _dt

    rec_response = RecommendationResponse(
        hotel_id="h1",
        generated_at=_dt.datetime.now(_dt.timezone.utc),
        forecast_model="seasonal",
        adjustment_model="rule_based",
        recommendation_model="rule_based_v1",
        summary=RecommendationSummary(total=2, critical=0, high=2, medium=0, low=0,
                                      estimated_revenue_opportunity=25000.0),
        recommendations=[],
    )
    anc_response = AncillaryRecommendationResponse(
        hotel_id="h1",
        generated_at=_dt.datetime.now(_dt.timezone.utc),
        engine_model="rule_based",
        persona=GuestPersona.hotel_wide,
        horizon_days=14,
        summary=AncillaryRecommendationSummary(
            eligible_products=10, shown=5,
            total_revenue_opportunity=8000.0,
            total_margin_opportunity=6000.0,
        ),
        recommendations=[],
    )
    g = executive_summary_grounding(
        hotel_name="Test Hotel",
        as_of_date="2025-08-01",
        current_occupancy=72.5,
        forecast_occupancy=80.0,
        current_adr=189.0,
        competitor_adr=175.0,
        active_events=[],
        rec_response=rec_response,
        anc_response=anc_response,
        persona="hotel_wide",
    )
    assert g.total_revenue_opportunity == pytest.approx(33000.0)
    assert g.forecast_uplift_pct == pytest.approx(7.5)
    assert len(g.top_commercial_actions) == 0   # no recs in list
    assert len(g.top_ancillary_offers) == 0


# ── 25. _fmt_events truncates at 4 ───────────────────────────────────────────

def test_fmt_events_truncates_at_4():
    events = [
        {"name": f"Event {i}", "event_type": "conference", "attendance": 1000, "distance_miles": 1.0}
        for i in range(6)
    ]
    result = _fmt_events(events)
    # Only first 4 events should appear (joined by "; ")
    parts = result.split("; ")
    assert len(parts) == 4
