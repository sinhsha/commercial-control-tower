"""
Unit tests for the RuleBasedEventEngineService.

All tests are purely in-memory – no database or HTTP transport.

Coverage map
────────────
1. No events → adjusted == baseline for every date
2. Single event, date inside window → positive uplift applied
3. Overlapping events → uplifts accumulate additively
4. Expired event (end_date < forecast_date) → no influence
5. Occupancy capped at 100 even with massive uplift
6. confidence=0.0 → contributes zero uplift
7. confidence=0.5 → uplift is exactly halved versus confidence=1.0
8. Negative event (weather_disruption) → adjusted < baseline
"""
from __future__ import annotations

import pytest
from datetime import date, timedelta

from app.models.demand_event import DemandEvent
from app.schemas.forecast import ForecastPoint
from app.services.event_engine.rule_based import RuleBasedEventEngineService
from app.services.events.default_impact import DefaultEventImpactService


# ── Helpers ───────────────────────────────────────────────────────────────────

_ORIGIN = date(2025, 6, 1)
_HOTEL_ID = "test-hotel"
_TOTAL_ROOMS = 300


def _make_baseline(days: int = 7, occupancy_pct: float = 70.0) -> list[ForecastPoint]:
    """Build a flat baseline ForecastPoint list starting the day after origin."""
    return [
        ForecastPoint(
            forecast_date=_ORIGIN + timedelta(days=i + 1),
            occupancy_pct=occupancy_pct,
            lower_bound=occupancy_pct - 5.0,
            upper_bound=occupancy_pct + 5.0,
        )
        for i in range(days)
    ]


def _make_event(
    event_type: str = "convention",
    start_offset: int = 1,   # days after origin
    duration: int = 3,
    distance_miles: float = 1.0,
    expected_attendance: int = 20_000,
    impact_strength: float = 0.8,
    confidence: float = 1.0,
) -> DemandEvent:
    start = _ORIGIN + timedelta(days=start_offset)
    end = start + timedelta(days=duration - 1)
    return DemandEvent(
        id="ev-1",
        hotel_id=_HOTEL_ID,
        name="Test Event",
        event_type=event_type,
        start_date=start,
        end_date=end,
        distance_miles=distance_miles,
        expected_attendance=expected_attendance,
        impact_strength=impact_strength,
        confidence=confidence,
        status="active",
    )


@pytest.fixture
def engine() -> RuleBasedEventEngineService:
    return RuleBasedEventEngineService(DefaultEventImpactService())


# ── 1. No events ──────────────────────────────────────────────────────────────

def test_no_events_adjusted_equals_baseline(engine: RuleBasedEventEngineService) -> None:
    """With zero events, adjusted occupancy must equal baseline for every date."""
    baseline = _make_baseline(days=7)
    result = engine.apply(
        hotel_id=_HOTEL_ID,
        hotel_total_rooms=_TOTAL_ROOMS,
        forecast_origin_date=_ORIGIN,
        baseline=baseline,
        events=[],
    )
    assert len(result) == len(baseline)
    for day, bp in zip(result, baseline):
        assert day.adjusted == bp.occupancy_pct
        assert day.uplift == 0.0
        assert day.reasons == []


# ── 2. Single event, date inside window ──────────────────────────────────────

def test_single_event_produces_positive_uplift(engine: RuleBasedEventEngineService) -> None:
    """A convention event starting on day+1 should lift day+1 occupancy."""
    event = _make_event(event_type="convention", start_offset=1, duration=1)
    baseline = _make_baseline(days=3)
    result = engine.apply(
        hotel_id=_HOTEL_ID,
        hotel_total_rooms=_TOTAL_ROOMS,
        forecast_origin_date=_ORIGIN,
        baseline=baseline,
        events=[event],
    )
    # Day 1 overlaps the event – should have positive uplift
    assert result[0].uplift > 0.0
    assert result[0].adjusted > result[0].baseline
    assert "Test Event" in result[0].reasons
    # Days 2 and 3 do not overlap – no uplift
    assert result[1].uplift == 0.0
    assert result[2].uplift == 0.0


# ── 3. Overlapping events ─────────────────────────────────────────────────────

def test_overlapping_events_uplifts_accumulate(engine: RuleBasedEventEngineService) -> None:
    """Two concurrent positive events on the same date should sum their uplifts."""
    ev1 = _make_event(event_type="convention", start_offset=1, duration=1)
    ev2 = DemandEvent(
        id="ev-2",
        hotel_id=_HOTEL_ID,
        name="Second Event",
        event_type="sports",
        start_date=_ORIGIN + timedelta(days=1),
        end_date=_ORIGIN + timedelta(days=1),
        distance_miles=1.0,
        expected_attendance=20_000,
        impact_strength=0.8,
        confidence=1.0,
        status="active",
    )
    baseline = _make_baseline(days=3)

    # Single event reference
    single = engine.apply(
        hotel_id=_HOTEL_ID,
        hotel_total_rooms=_TOTAL_ROOMS,
        forecast_origin_date=_ORIGIN,
        baseline=baseline,
        events=[ev1],
    )

    # Both events together
    combined = engine.apply(
        hotel_id=_HOTEL_ID,
        hotel_total_rooms=_TOTAL_ROOMS,
        forecast_origin_date=_ORIGIN,
        baseline=baseline,
        events=[ev1, ev2],
    )

    assert combined[0].uplift > single[0].uplift
    assert len(combined[0].influences) == 2


# ── 4. Expired / future event that does not cover forecast date ───────────────

def test_event_outside_forecast_dates_ignored(engine: RuleBasedEventEngineService) -> None:
    """An event whose window doesn't cover any forecast date contributes nothing."""
    # Event starts 10 days after origin, baseline only covers days 1–3
    event = _make_event(start_offset=10, duration=2)
    baseline = _make_baseline(days=3)
    result = engine.apply(
        hotel_id=_HOTEL_ID,
        hotel_total_rooms=_TOTAL_ROOMS,
        forecast_origin_date=_ORIGIN,
        baseline=baseline,
        events=[event],
    )
    for day in result:
        assert day.uplift == 0.0


# ── 5. Occupancy capped at 100 ────────────────────────────────────────────────

def test_adjusted_occupancy_never_exceeds_100(engine: RuleBasedEventEngineService) -> None:
    """Even with a massive uplift, adjusted occupancy must stay ≤ 100."""
    # Start at 98% occupancy
    baseline = [
        ForecastPoint(
            forecast_date=_ORIGIN + timedelta(days=1),
            occupancy_pct=98.0,
            lower_bound=93.0,
            upper_bound=100.0,
        )
    ]
    event = _make_event(
        event_type="convention",
        start_offset=1,
        duration=1,
        distance_miles=0.1,
        expected_attendance=500_000,
        impact_strength=1.0,
        confidence=1.0,
    )
    result = engine.apply(
        hotel_id=_HOTEL_ID,
        hotel_total_rooms=_TOTAL_ROOMS,
        forecast_origin_date=_ORIGIN,
        baseline=baseline,
        events=[event],
    )
    assert result[0].adjusted <= 100.0
    assert result[0].confidence_high <= 100.0


# ── 6. confidence=0.0 → zero contribution ────────────────────────────────────

def test_zero_confidence_event_contributes_no_uplift(engine: RuleBasedEventEngineService) -> None:
    """An event with confidence=0.0 should not change any occupancy values."""
    event = _make_event(confidence=0.0)
    baseline = _make_baseline(days=3)
    result = engine.apply(
        hotel_id=_HOTEL_ID,
        hotel_total_rooms=_TOTAL_ROOMS,
        forecast_origin_date=_ORIGIN,
        baseline=baseline,
        events=[event],
    )
    for day in result:
        assert day.uplift == 0.0
        assert day.adjusted == day.baseline


# ── 7. confidence=0.5 halves uplift vs confidence=1.0 ────────────────────────

def test_half_confidence_halves_uplift(engine: RuleBasedEventEngineService) -> None:
    """
    Uplift for confidence=0.5 should be approximately half of confidence=1.0.
    Uses the same event geometry so only the confidence weight differs.
    """
    baseline = _make_baseline(days=1, occupancy_pct=50.0)

    full_event = _make_event(start_offset=1, duration=1, confidence=1.0)
    half_event = _make_event(start_offset=1, duration=1, confidence=0.5)

    full_result = engine.apply(
        hotel_id=_HOTEL_ID,
        hotel_total_rooms=_TOTAL_ROOMS,
        forecast_origin_date=_ORIGIN,
        baseline=baseline,
        events=[full_event],
    )
    half_result = engine.apply(
        hotel_id=_HOTEL_ID,
        hotel_total_rooms=_TOTAL_ROOMS,
        forecast_origin_date=_ORIGIN,
        baseline=baseline,
        events=[half_event],
    )

    full_uplift = full_result[0].uplift
    half_uplift = half_result[0].uplift

    # Allow for floating-point rounding tolerance (± 0.2 pp)
    assert abs(half_uplift - full_uplift / 2) < 0.2


# ── 8. Negative event (weather_disruption) ───────────────────────────────────

def test_negative_event_reduces_adjusted_below_baseline(
    engine: RuleBasedEventEngineService,
) -> None:
    """A weather disruption should produce a negative uplift, lowering occupancy."""
    event = _make_event(
        event_type="weather_disruption",
        start_offset=1,
        duration=1,
        distance_miles=0.0,
        expected_attendance=10_000,   # non-zero so capacity_ratio > 0
        impact_strength=0.8,
        confidence=1.0,
    )
    baseline = _make_baseline(days=3, occupancy_pct=70.0)
    result = engine.apply(
        hotel_id=_HOTEL_ID,
        hotel_total_rooms=_TOTAL_ROOMS,
        forecast_origin_date=_ORIGIN,
        baseline=baseline,
        events=[event],
    )
    # Day 1 should have negative uplift and adjusted < baseline
    assert result[0].uplift < 0.0
    assert result[0].adjusted < result[0].baseline
    assert result[0].adjusted >= 0.0  # clamped, never negative
