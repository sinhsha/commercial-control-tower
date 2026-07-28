"""
Unit tests for the event-impact service layer.

All tests are purely in-memory – no database or HTTP transport.
"""
from __future__ import annotations

import pytest
from datetime import date, timedelta

from app.services.events.default_impact import DefaultEventImpactService
from app.models.demand_event import DemandEvent


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_event(
    event_type: str = "convention",
    start_offset: int = 2,      # days from today
    duration: int = 3,
    distance_miles: float = 1.0,
    expected_attendance: int = 10_000,
    impact_strength: float = 0.8,
    status: str = "active",
) -> DemandEvent:
    today = date.today()
    start = today + timedelta(days=start_offset)
    end = start + timedelta(days=duration - 1)
    return DemandEvent(
        id="test-event-id",
        hotel_id="test-hotel-id",
        name="Test Event",
        event_type=event_type,
        start_date=start,
        end_date=end,
        distance_miles=distance_miles,
        expected_attendance=expected_attendance,
        impact_strength=impact_strength,
        status=status,
    )


@pytest.fixture
def svc() -> DefaultEventImpactService:
    return DefaultEventImpactService()


# ── No active events ──────────────────────────────────────────────────────────

def test_no_influence_when_date_outside_event_window(svc: DefaultEventImpactService) -> None:
    event = _make_event(start_offset=5, duration=3)  # event runs days +5 to +7
    forecast_date = event.start_date - timedelta(days=1)  # day before
    result = svc.compute_uplift(
        forecast_date=forecast_date,
        event=event,
        hotel_total_rooms=300,
        days_until_event=5,
    )
    assert result is None


def test_no_influence_after_event_end(svc: DefaultEventImpactService) -> None:
    event = _make_event(start_offset=5, duration=3)
    forecast_date = event.end_date + timedelta(days=1)
    result = svc.compute_uplift(
        forecast_date=forecast_date,
        event=event,
        hotel_total_rooms=300,
        days_until_event=5,
    )
    assert result is None


# ── One event ─────────────────────────────────────────────────────────────────

def test_convention_produces_positive_uplift(svc: DefaultEventImpactService) -> None:
    event = _make_event(event_type="convention", start_offset=3, duration=2)
    result = svc.compute_uplift(
        forecast_date=event.start_date,
        event=event,
        hotel_total_rooms=300,
        days_until_event=3,
    )
    assert result is not None
    assert result.uplift_points > 0
    assert result.event_type == "convention"


def test_weather_disruption_produces_negative_uplift(svc: DefaultEventImpactService) -> None:
    event = _make_event(event_type="weather_disruption", start_offset=1, duration=2)
    result = svc.compute_uplift(
        forecast_date=event.start_date,
        event=event,
        hotel_total_rooms=300,
        days_until_event=1,
    )
    assert result is not None
    assert result.uplift_points < 0


def test_flight_disruption_produces_negative_uplift(svc: DefaultEventImpactService) -> None:
    event = _make_event(event_type="flight_disruption", start_offset=2, duration=1)
    result = svc.compute_uplift(
        forecast_date=event.start_date,
        event=event,
        hotel_total_rooms=200,
        days_until_event=2,
    )
    assert result is not None
    assert result.uplift_points < 0


def test_influence_contains_explanation(svc: DefaultEventImpactService) -> None:
    event = _make_event(event_type="sports", start_offset=4, duration=1)
    result = svc.compute_uplift(
        forecast_date=event.start_date,
        event=event,
        hotel_total_rooms=300,
        days_until_event=4,
    )
    assert result is not None
    assert len(result.explanation) > 10
    assert result.event_name == "Test Event"


# ── Overlapping events ────────────────────────────────────────────────────────

def test_multiple_events_on_same_date_uplift_accumulates(
    svc: DefaultEventImpactService,
) -> None:
    today = date.today()
    target = today + timedelta(days=3)

    events = [
        _make_event(event_type="convention", start_offset=3, duration=1),
        _make_event(event_type="concert", start_offset=3, duration=1),
    ]

    total_uplift = 0.0
    for ev in events:
        r = svc.compute_uplift(
            forecast_date=target,
            event=ev,
            hotel_total_rooms=300,
            days_until_event=3,
        )
        if r is not None:
            total_uplift += r.uplift_points

    # Two positive events on the same day should both contribute
    assert total_uplift > 0


# ── Distance decay ────────────────────────────────────────────────────────────

def test_distant_event_has_lower_impact(svc: DefaultEventImpactService) -> None:
    nearby = _make_event(distance_miles=0.5, start_offset=3, duration=1)
    far = _make_event(distance_miles=50.0, start_offset=3, duration=1)

    r_nearby = svc.compute_uplift(
        forecast_date=nearby.start_date,
        event=nearby,
        hotel_total_rooms=300,
        days_until_event=3,
    )
    r_far = svc.compute_uplift(
        forecast_date=far.start_date,
        event=far,
        hotel_total_rooms=300,
        days_until_event=3,
    )
    assert r_nearby is not None
    # Far event should produce less uplift (or be filtered as negligible)
    far_pts = r_far.uplift_points if r_far else 0.0
    assert r_nearby.uplift_points > far_pts


# ── Occupancy bounds – uplift must not push beyond 0–100 ─────────────────────

def test_adjusted_occupancy_stays_within_bounds() -> None:
    """
    Simulates the endpoint's clamp logic: even if uplift is large,
    adjusted occupancy cannot exceed 100.
    """
    def clamp(v: float) -> float:
        return max(0.0, min(100.0, v))

    baseline_occ = 95.0
    uplift = 20.0  # would push to 115
    adjusted = clamp(baseline_occ + uplift)
    assert adjusted == 100.0

    baseline_occ = 5.0
    negative_uplift = -20.0  # would push to -15
    adjusted = clamp(baseline_occ + negative_uplift)
    assert adjusted == 0.0


# ── Event outside forecast horizon ───────────────────────────────────────────

def test_event_outside_forecast_window_returns_none(svc: DefaultEventImpactService) -> None:
    """
    If the forecast date is before the event starts, no influence should
    be returned, regardless of proximity settings.
    """
    event = _make_event(start_offset=20, duration=3)
    # Forecast date well before the event
    forecast_date = date.today() + timedelta(days=5)
    assert forecast_date < event.start_date  # sanity

    result = svc.compute_uplift(
        forecast_date=forecast_date,
        event=event,
        hotel_total_rooms=300,
        days_until_event=20,
    )
    assert result is None


def test_last_day_of_event_is_included(svc: DefaultEventImpactService) -> None:
    event = _make_event(start_offset=2, duration=3)
    result = svc.compute_uplift(
        forecast_date=event.end_date,
        event=event,
        hotel_total_rooms=300,
        days_until_event=2,
    )
    assert result is not None


# ── Proximity discount reduces far-future events ─────────────────────────────

def test_proximity_discount_reduces_uplift_for_far_future(
    svc: DefaultEventImpactService,
) -> None:
    near = _make_event(start_offset=5, duration=1)
    far_future = _make_event(start_offset=85, duration=1)

    r_near = svc.compute_uplift(
        forecast_date=near.start_date,
        event=near,
        hotel_total_rooms=300,
        days_until_event=5,
    )
    r_far = svc.compute_uplift(
        forecast_date=far_future.start_date,
        event=far_future,
        hotel_total_rooms=300,
        days_until_event=85,
    )
    near_pts = r_near.uplift_points if r_near else 0.0
    far_pts = r_far.uplift_points if r_far else 0.0
    assert near_pts > far_pts
