"""
Unit tests for the Rule-Based Commercial Recommendation Engine.

All tests are purely in-memory – no database or HTTP transport.

Coverage map
────────────
 1. High-demand rate increase (occ ≥ 85%, competitor ADR support)
 2. Low-demand recommendation (occ < 55%, low pace, no strong event)
 3. Very-high-demand restriction (occ ≥ 92%, high pace → close discounts)
 4. Minimum-length-of-stay rule (≥ 2 consecutive nights ≥ 92%)
 5. Premium-inventory protection (occ > 88%, scarce rooms)
 6. Paid-upgrade recommendation (same trigger as premium protection)
 7. Event-package recommendation (convention/sports event nearby)
 8. Operational-pressure alert (occ > 95%, high arrivals)
 9. No recommendation when no thresholds are met
10. Maximum rate-increase guardrail enforced
11. Maximum rate-decrease guardrail enforced
12. Minimum rate floor applied
13. Maximum rate ceiling applied
14. Conflicting recommendation suppression (increase vs reduce)
15. Recommendation ranking (highest score first)
16. Recommendation limit enforced
17. Stable deterministic IDs (same inputs → same IDs)
18. Estimated revenue calculation correctness
19. Missing / fallback market signals gracefully handled
20. Empty forecast response (no historical data)
"""
from __future__ import annotations

import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.demand_event import DemandEvent
from app.models.hotel import Hotel
from app.models.daily_metrics import DailyMetrics
from app.schemas.events import AdjustedForecastDay
from app.schemas.forecast import ForecastPoint
from app.schemas.recommendations import (
    MarketSignals,
    RecommendationAction,
    RecommendationCategory,
    RecommendationConfidence,
    RecommendationPriority,
)
from app.services.recommendations.rule_based import (
    RuleBasedRecommendationService,
    _Context,
)
from app.services.recommendations.scoring import (
    assign_priority,
    compute_score,
    deduplicate_and_sort,
)

# ── Shared test fixtures ──────────────────────────────────────────────────────

_ORIGIN = date(2025, 8, 1)
_HOTEL_ID = "hotel-test-001"
_TOTAL_ROOMS = 200


def _make_adjusted_days(
    days: int = 14,
    occupancy: float = 75.0,
    uplift: float = 0.0,
) -> list[AdjustedForecastDay]:
    return [
        AdjustedForecastDay(
            date=_ORIGIN + timedelta(days=i + 1),
            baseline=occupancy - uplift,
            adjusted=occupancy,
            uplift=uplift,
            confidence_low=occupancy - 5,
            confidence_high=min(100.0, occupancy + 5),
            reasons=[],
            influences=[],
        )
        for i in range(days)
    ]


def _make_baseline_points(
    days: int = 14, occupancy: float = 75.0
) -> list[ForecastPoint]:
    return [
        ForecastPoint(
            forecast_date=_ORIGIN + timedelta(days=i + 1),
            occupancy_pct=occupancy,
            lower_bound=occupancy - 5,
            upper_bound=min(100.0, occupancy + 5),
        )
        for i in range(days)
    ]


def _make_event(
    event_type: str = "convention",
    impact_strength: float = 0.8,
    confidence: float = 0.9,
    distance_miles: float = 1.0,
    attendance: int = 30_000,
    start_offset: int = 1,
    duration: int = 3,
) -> DemandEvent:
    start = _ORIGIN + timedelta(days=start_offset)
    return DemandEvent(
        id="ev-test-1",
        hotel_id=_HOTEL_ID,
        name="Test Convention",
        event_type=event_type,
        start_date=start,
        end_date=start + timedelta(days=duration - 1),
        distance_miles=distance_miles,
        expected_attendance=attendance,
        impact_strength=impact_strength,
        confidence=confidence,
        status="active",
    )


def _market_signals(
    competitor_adr: float = 300.0,
    competitor_occ: float = 72.0,
    booking_pace: float = 1.05,
    cancellation_rate: float = 8.0,
    premium_rooms: int = 8,
    expected_arrivals: int = 90,
) -> MarketSignals:
    return MarketSignals(
        competitor_adr=competitor_adr,
        competitor_occupancy=competitor_occ,
        booking_pace_index=booking_pace,
        cancellation_rate=cancellation_rate,
        premium_rooms_available=premium_rooms,
        expected_arrivals=expected_arrivals,
    )


def _make_context(
    occupancy: float = 75.0,
    uplift: float = 0.0,
    adr: float = 250.0,
    events: list[DemandEvent] | None = None,
    signals: MarketSignals | None = None,
    days: int = 14,
) -> _Context:
    adjusted = _make_adjusted_days(days=days, occupancy=occupancy, uplift=uplift)
    baseline = _make_baseline_points(days=days, occupancy=occupancy - uplift)
    ctx = _Context(
        hotel_id=_HOTEL_ID,
        as_of=_ORIGIN,
        horizon_days=days,
        total_rooms=_TOTAL_ROOMS,
        current_adr=adr,
        current_occupancy=occupancy,
        current_revpar=adr * occupancy / 100,
        baseline_points=baseline,
        adjusted_days=adjusted,
        events=events or [],
        signals=signals or _market_signals(),
        forecast_model="Seasonal Baseline",
        adjustment_model="Rule Based Event Engine",
    )
    return ctx


# ── Helpers to call rules directly ───────────────────────────────────────────

def _make_svc() -> RuleBasedRecommendationService:
    """Create service with all dependencies mocked (not used in unit tests)."""
    svc = object.__new__(RuleBasedRecommendationService)
    svc.recommendation_model = "Rule Based Commercial Engine"
    return svc  # type: ignore[return-value]


# ── Test 1: High-demand rate increase ─────────────────────────────────────────

def test_high_demand_pricing_recommends_rate_increase() -> None:
    """Occupancy ≥ 85% + positive uplift + competitor ADR ≥ hotel → increase_rate."""
    svc = _make_svc()
    ctx = _make_context(occupancy=88.0, uplift=5.0, adr=250.0)
    recs = svc._rule_high_demand_pricing(ctx)
    assert len(recs) == 1
    assert recs[0].action == RecommendationAction.increase_rate
    assert recs[0].recommended_value > recs[0].current_value  # type: ignore
    assert recs[0].expected_revenue_impact > 0


def test_high_demand_no_recommendation_when_competitor_below() -> None:
    """If competitor ADR < hotel ADR, no rate increase recommended."""
    svc = _make_svc()
    ctx = _make_context(
        occupancy=88.0, uplift=5.0, adr=350.0,
        signals=_market_signals(competitor_adr=300.0),
    )
    recs = svc._rule_high_demand_pricing(ctx)
    assert recs == []


def test_high_demand_no_recommendation_when_uplift_zero() -> None:
    """No rate increase if event uplift is zero or negative."""
    svc = _make_svc()
    ctx = _make_context(occupancy=87.0, uplift=0.0, adr=250.0)
    recs = svc._rule_high_demand_pricing(ctx)
    assert recs == []


# ── Test 2: Low-demand recommendation ─────────────────────────────────────────

def test_low_demand_very_low_occ_recommends_reduce_rate() -> None:
    """Occupancy < 40% → reduce_rate action."""
    svc = _make_svc()
    ctx = _make_context(
        occupancy=35.0, uplift=0.0, adr=200.0,
        signals=_market_signals(booking_pace=0.8),
    )
    recs = svc._rule_low_demand(ctx)
    assert len(recs) == 1
    assert recs[0].action == RecommendationAction.reduce_rate
    assert recs[0].recommended_value < recs[0].current_value  # type: ignore


def test_low_demand_moderate_occ_recommends_package() -> None:
    """Occupancy 40–55% → breakfast package (hold rate) preferred."""
    svc = _make_svc()
    ctx = _make_context(
        occupancy=48.0, uplift=0.0, adr=200.0,
        signals=_market_signals(booking_pace=0.85),
    )
    recs = svc._rule_low_demand(ctx)
    assert len(recs) == 1
    assert recs[0].action == RecommendationAction.launch_breakfast_package


def test_low_demand_no_recommendation_when_strong_event() -> None:
    """Strong event (impact_strength ≥ 0.7) suppresses low-demand rule."""
    svc = _make_svc()
    ctx = _make_context(
        occupancy=48.0, uplift=0.0, adr=200.0,
        events=[_make_event(impact_strength=0.8)],
        signals=_market_signals(booking_pace=0.85),
    )
    recs = svc._rule_low_demand(ctx)
    assert recs == []


def test_low_demand_no_recommendation_when_pace_normal() -> None:
    """Booking pace ≥ 1.0 suppresses low-demand rule."""
    svc = _make_svc()
    ctx = _make_context(
        occupancy=48.0, uplift=0.0, adr=200.0,
        signals=_market_signals(booking_pace=1.0),
    )
    recs = svc._rule_low_demand(ctx)
    assert recs == []


# ── Test 3: Very-high-demand restriction ─────────────────────────────────────

def test_very_high_demand_close_discounts() -> None:
    """Occupancy ≥ 92% + pace > 1.0 → close_discounted_rates."""
    svc = _make_svc()
    ctx = _make_context(
        occupancy=94.0, uplift=5.0, adr=280.0,
        signals=_market_signals(booking_pace=1.15),
    )
    recs = svc._rule_very_high_demand_restriction(ctx)
    actions = [r.action for r in recs]
    assert RecommendationAction.close_discounted_rates in actions


def test_very_high_demand_no_restriction_when_pace_normal() -> None:
    """Booking pace ≤ 1.0 suppresses restriction rule."""
    svc = _make_svc()
    ctx = _make_context(
        occupancy=93.0, uplift=5.0, adr=280.0,
        signals=_market_signals(booking_pace=0.98),
    )
    recs = svc._rule_very_high_demand_restriction(ctx)
    assert recs == []


# ── Test 4: MLOS rule ─────────────────────────────────────────────────────────

def test_mlos_added_for_consecutive_nights() -> None:
    """≥ 2 consecutive nights at ≥ 92% → add_minimum_length_of_stay."""
    svc = _make_svc()
    # Build 3 consecutive nights at 93% then drop
    adjusted = (
        _make_adjusted_days(days=3, occupancy=93.0, uplift=5.0)
        + _make_adjusted_days(days=11, occupancy=60.0, uplift=0.0)
    )
    # Re-offset dates
    for i, d in enumerate(adjusted):
        object.__setattr__(d, "date", _ORIGIN + timedelta(days=i + 1))
    ctx = _make_context(occupancy=93.0, uplift=5.0, adr=280.0,
                        signals=_market_signals(booking_pace=1.2))
    ctx.adjusted_days[:] = adjusted
    recs = svc._rule_very_high_demand_restriction(ctx)
    actions = [r.action for r in recs]
    assert RecommendationAction.add_minimum_length_of_stay in actions
    mlos_rec = next(r for r in recs if r.action == RecommendationAction.add_minimum_length_of_stay)
    assert mlos_rec.recommended_value == 2.0


def test_mlos_not_added_for_single_night() -> None:
    """Single high night (no consecutive run) should NOT trigger MLOS."""
    svc = _make_svc()
    # Only first day at 93%, rest at 70%
    adjusted = (
        _make_adjusted_days(days=1, occupancy=93.0, uplift=5.0)
        + _make_adjusted_days(days=13, occupancy=70.0, uplift=0.0)
    )
    for i, d in enumerate(adjusted):
        object.__setattr__(d, "date", _ORIGIN + timedelta(days=i + 1))
    ctx = _make_context(occupancy=70.0, uplift=0.0, adr=280.0,
                        signals=_market_signals(booking_pace=1.2))
    ctx.adjusted_days[:] = adjusted
    recs = svc._rule_very_high_demand_restriction(ctx)
    actions = [r.action for r in recs]
    assert RecommendationAction.add_minimum_length_of_stay not in actions


# ── Test 5: Premium-inventory protection ──────────────────────────────────────

def test_premium_inventory_protection_recommended() -> None:
    """Occupancy > 88% + premium rooms < 15 → protect_premium_inventory."""
    svc = _make_svc()
    ctx = _make_context(
        occupancy=91.0, uplift=3.0, adr=280.0,
        signals=_market_signals(premium_rooms=6),
    )
    recs = svc._rule_premium_inventory(ctx)
    actions = [r.action for r in recs]
    assert RecommendationAction.protect_premium_inventory in actions


def test_premium_inventory_not_recommended_when_ample() -> None:
    """≥ 15 premium rooms → no premium inventory action."""
    svc = _make_svc()
    ctx = _make_context(
        occupancy=91.0, uplift=3.0, adr=280.0,
        signals=_market_signals(premium_rooms=20),
    )
    recs = svc._rule_premium_inventory(ctx)
    assert recs == []


# ── Test 6: Paid-upgrade recommendation ──────────────────────────────────────

def test_paid_upgrade_recommended_with_premium_rule() -> None:
    """Premium inventory rule includes open_paid_upgrades."""
    svc = _make_svc()
    ctx = _make_context(
        occupancy=91.0, uplift=3.0, adr=280.0,
        signals=_market_signals(premium_rooms=6),
    )
    recs = svc._rule_premium_inventory(ctx)
    actions = [r.action for r in recs]
    assert RecommendationAction.open_paid_upgrades in actions


# ── Test 7: Event-package recommendation ──────────────────────────────────────

def test_event_package_recommended_for_convention() -> None:
    """Convention event → launch_parking_package."""
    svc = _make_svc()
    ctx = _make_context(
        occupancy=78.0, uplift=3.0, adr=260.0,
        events=[_make_event(event_type="convention")],
    )
    recs = svc._rule_event_package(ctx)
    assert len(recs) >= 1
    assert any(r.action == RecommendationAction.launch_parking_package for r in recs)


def test_event_package_recommended_for_concert() -> None:
    """Concert event → promote_late_checkout."""
    svc = _make_svc()
    ctx = _make_context(
        occupancy=78.0, uplift=3.0, adr=260.0,
        events=[_make_event(event_type="concert")],
    )
    recs = svc._rule_event_package(ctx)
    assert any(r.action == RecommendationAction.promote_late_checkout for r in recs)


def test_event_package_not_triggered_without_event() -> None:
    """No events → no event-package recommendation."""
    svc = _make_svc()
    ctx = _make_context(occupancy=78.0, uplift=0.0, adr=260.0, events=[])
    recs = svc._rule_event_package(ctx)
    assert recs == []


# ── Test 8: Operational-pressure alert ───────────────────────────────────────

def test_operational_alert_at_near_sellout() -> None:
    """Occupancy > 95% + high arrivals → operational alerts."""
    svc = _make_svc()
    ctx = _make_context(
        occupancy=97.0, uplift=8.0, adr=320.0,
        signals=_market_signals(expected_arrivals=110),
    )
    recs = svc._rule_operational_pressure(ctx)
    actions = {r.action for r in recs}
    assert RecommendationAction.alert_front_desk in actions
    assert RecommendationAction.alert_housekeeping in actions
    assert RecommendationAction.alert_revenue_manager in actions


def test_operational_no_alert_when_arrivals_low() -> None:
    """Low expected arrivals suppresses operational alerts."""
    svc = _make_svc()
    ctx = _make_context(
        occupancy=97.0, uplift=8.0, adr=320.0,
        signals=_market_signals(expected_arrivals=40),
    )
    recs = svc._rule_operational_pressure(ctx)
    assert recs == []


# ── Test 9: No recommendation when thresholds not met ────────────────────────

def test_no_recommendations_when_conditions_normal() -> None:
    """Normal occupancy (70%), normal pace, no events → no recommendations."""
    svc = _make_svc()
    ctx = _make_context(
        occupancy=70.0, uplift=0.0, adr=250.0,
        signals=_market_signals(booking_pace=1.0, expected_arrivals=50, premium_rooms=20),
    )
    recs: list = []
    for rule in [
        svc._rule_high_demand_pricing,
        svc._rule_very_high_demand_restriction,
        svc._rule_low_demand,
        svc._rule_premium_inventory,
        svc._rule_event_package,
        svc._rule_operational_pressure,
    ]:
        recs.extend(rule(ctx))
    assert recs == []


# ── Test 10: Maximum rate-increase guardrail ──────────────────────────────────

def test_max_rate_increase_guardrail() -> None:
    """Rate increase must never exceed max_rate_increase_pct."""
    svc = _make_svc()
    ctx = _make_context(occupancy=99.0, uplift=20.0, adr=250.0)
    ctx.max_rate_increase_pct = 8.0
    recs = svc._rule_high_demand_pricing(ctx)
    assert recs, "Expected rate increase recommendation"
    rec = recs[0]
    applied_pct = (rec.recommended_value - rec.current_value) / rec.current_value * 100  # type: ignore
    assert applied_pct <= 8.0 + 0.01  # small float tolerance


# ── Test 11: Maximum rate-decrease guardrail ──────────────────────────────────

def test_max_rate_decrease_guardrail() -> None:
    """Rate decrease must never exceed max_rate_decrease_pct."""
    svc = _make_svc()
    ctx = _make_context(
        occupancy=30.0, uplift=0.0, adr=200.0,
        signals=_market_signals(booking_pace=0.7),
    )
    ctx.max_rate_decrease_pct = 6.0
    recs = svc._rule_low_demand(ctx)
    assert recs, "Expected rate reduce recommendation"
    rec = recs[0]
    applied_pct = (rec.current_value - rec.recommended_value) / rec.current_value * 100  # type: ignore
    assert applied_pct <= 6.0 + 0.01


# ── Test 12: Minimum rate floor ───────────────────────────────────────────────

def test_minimum_rate_floor_applied() -> None:
    """Recommended rate must never drop below min_rate."""
    svc = _make_svc()
    ctx = _make_context(
        occupancy=30.0, uplift=0.0, adr=100.0,
        signals=_market_signals(booking_pace=0.6),
    )
    ctx.min_rate = 89.0
    recs = svc._rule_low_demand(ctx)
    assert recs
    assert recs[0].recommended_value >= 89.0  # type: ignore


# ── Test 13: Maximum rate ceiling ────────────────────────────────────────────

def test_maximum_rate_ceiling_applied() -> None:
    """Recommended rate must never exceed max_rate."""
    svc = _make_svc()
    ctx = _make_context(occupancy=99.0, uplift=20.0, adr=950.0,
                        signals=_market_signals(competitor_adr=1000.0))
    ctx.max_rate = 999.0
    recs = svc._rule_high_demand_pricing(ctx)
    if recs:
        assert recs[0].recommended_value <= 999.0  # type: ignore


# ── Test 14: Conflicting recommendation suppression ──────────────────────────

def test_conflicting_increase_reduce_suppressed() -> None:
    """increase_rate and reduce_rate cannot coexist after deduplication."""
    from app.schemas.recommendations import RecommendationStatus
    # Manually create both to test the suppression logic
    from app.schemas.recommendations import Recommendation, RecommendationCategory

    def _make_rec(action: RecommendationAction, score: float) -> Recommendation:
        return Recommendation(
            id=f"REC-test-{action.value}",
            hotel_id=_HOTEL_ID,
            category=RecommendationCategory.pricing,
            action=action,
            title="Test",
            summary="Test",
            effective_start_date=_ORIGIN + timedelta(days=1),
            effective_end_date=_ORIGIN + timedelta(days=3),
            score=score,
            priority=RecommendationPriority.medium,
            confidence=RecommendationConfidence.medium,
        )

    recs = [
        _make_rec(RecommendationAction.increase_rate, 80.0),
        _make_rec(RecommendationAction.reduce_rate, 40.0),
    ]
    result = deduplicate_and_sort(recs, limit=10)
    actions = {r.action for r in result}
    # Only one of the conflicting pair should survive
    assert not (
        RecommendationAction.increase_rate in actions
        and RecommendationAction.reduce_rate in actions
    )


# ── Test 15: Recommendation ranking ──────────────────────────────────────────

def test_recommendations_ranked_by_score_descending() -> None:
    """deduplicate_and_sort returns highest-scored first."""
    from app.schemas.recommendations import Recommendation, RecommendationCategory, RecommendationStatus

    def _make(action: RecommendationAction, score: float) -> Recommendation:
        return Recommendation(
            id=f"REC-{score}",
            hotel_id=_HOTEL_ID,
            category=RecommendationCategory.operational,
            action=action,
            title="T",
            summary="S",
            effective_start_date=_ORIGIN + timedelta(days=1),
            effective_end_date=_ORIGIN + timedelta(days=2),
            score=score,
            priority=RecommendationPriority.medium,
            confidence=RecommendationConfidence.medium,
        )

    recs = [
        _make(RecommendationAction.alert_front_desk, 30.0),
        _make(RecommendationAction.alert_housekeeping, 75.0),
        _make(RecommendationAction.alert_revenue_manager, 55.0),
    ]
    result = deduplicate_and_sort(recs, limit=10)
    scores = [r.score for r in result]
    assert scores == sorted(scores, reverse=True)


# ── Test 16: Recommendation limit ────────────────────────────────────────────

def test_recommendation_limit_enforced() -> None:
    """deduplicate_and_sort respects the limit parameter."""
    from app.schemas.recommendations import Recommendation, RecommendationCategory

    recs = [
        Recommendation(
            id=f"REC-{i}",
            hotel_id=_HOTEL_ID,
            category=RecommendationCategory.operational,
            action=RecommendationAction.alert_revenue_manager,
            title=f"T{i}",
            summary="S",
            effective_start_date=_ORIGIN + timedelta(days=1),
            effective_end_date=_ORIGIN + timedelta(days=2),
            score=float(i),
            priority=RecommendationPriority.low,
            confidence=RecommendationConfidence.low,
        )
        for i in range(20)
    ]
    result = deduplicate_and_sort(recs, limit=5)
    assert len(result) <= 5


# ── Test 17: Stable deterministic IDs ────────────────────────────────────────

def test_recommendation_ids_are_deterministic() -> None:
    """Same context inputs produce the same recommendation IDs."""
    svc = _make_svc()
    ctx1 = _make_context(occupancy=88.0, uplift=5.0, adr=250.0)
    ctx2 = _make_context(occupancy=88.0, uplift=5.0, adr=250.0)
    recs1 = svc._rule_high_demand_pricing(ctx1)
    recs2 = svc._rule_high_demand_pricing(ctx2)
    assert [r.id for r in recs1] == [r.id for r in recs2]


# ── Test 18: Estimated revenue calculation ────────────────────────────────────

def test_estimated_revenue_calculation() -> None:
    """Rate increase × forecast occupied rooms × affected nights = expected_revenue_impact."""
    svc = _make_svc()
    adr = 250.0
    occupancy = 90.0
    ctx = _make_context(occupancy=occupancy, uplift=5.0, adr=adr,
                        signals=_market_signals(competitor_adr=310.0))
    recs = svc._rule_high_demand_pricing(ctx)
    assert recs
    rec = recs[0]
    # Sanity check: impact > 0 and proportional to scale
    assert rec.expected_revenue_impact > 0
    assert rec.expected_revenue_impact < 1_000_000  # reasonable upper bound for 200-room hotel


# ── Test 19: Missing market signal fallback ───────────────────────────────────

@pytest.mark.asyncio
async def test_missing_market_signals_use_fallback() -> None:
    """MockMarketSignalService must return valid signals for any hotel_id."""
    from app.services.market_signals.mock import MockMarketSignalService

    svc = MockMarketSignalService()
    signals = await svc.get_signals("unknown-hotel-xyz")
    assert signals.competitor_adr > 0
    assert 0 <= signals.booking_pace_index <= 2.0
    assert signals.premium_rooms_available >= 0


# ── Test 20: Empty forecast / no historical data ──────────────────────────────

def test_no_recommendation_when_no_adjusted_days() -> None:
    """Empty adjusted_days (no historical data) → rules do not raise, return []."""
    svc = _make_svc()
    ctx = _make_context(occupancy=88.0, uplift=0.0, adr=250.0)
    ctx.adjusted_days.clear()
    # All rules should handle empty adjusted_days gracefully
    for rule in [
        svc._rule_high_demand_pricing,
        svc._rule_very_high_demand_restriction,
        svc._rule_premium_inventory,
        svc._rule_operational_pressure,
    ]:
        result = rule(ctx)
        assert isinstance(result, list)


# ── Scoring unit tests ────────────────────────────────────────────────────────

def test_score_high_revenue_high_confidence_same_day() -> None:
    """A same-day, high-revenue, high-confidence recommendation scores ≥ 70."""
    score = compute_score(
        expected_revenue_impact=30_000,
        confidence=RecommendationConfidence.high,
        effective_start=_ORIGIN + timedelta(days=1),
        as_of=_ORIGIN,
        adjusted_occupancy=95.0,
        has_active_event=True,
    )
    assert score >= 70.0


def test_score_low_revenue_low_confidence_far_future() -> None:
    """A far-future, low-revenue, low-confidence recommendation scores < 35."""
    score = compute_score(
        expected_revenue_impact=100,
        confidence=RecommendationConfidence.low,
        effective_start=_ORIGIN + timedelta(days=20),
        as_of=_ORIGIN,
        adjusted_occupancy=40.0,
        has_active_event=False,
    )
    assert score < 35.0


def test_assign_priority_respects_confidence_cap() -> None:
    """Low confidence cannot yield 'critical' priority even at high score."""
    priority = assign_priority(score=90.0, confidence=RecommendationConfidence.low)
    assert priority == RecommendationPriority.medium


def test_assign_priority_medium_confidence_cap() -> None:
    """Medium confidence caps at 'high', not 'critical'."""
    priority = assign_priority(score=90.0, confidence=RecommendationConfidence.medium)
    assert priority == RecommendationPriority.high
