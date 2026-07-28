"""
Unit tests for the forecasting service layer.

These tests operate entirely against the service classes and helper
functions in memory – no database, no HTTP transport required.
"""
from __future__ import annotations

import pytest
from datetime import date, timedelta

from app.services.forecasting.seasonal_baseline import (
    SeasonalBaselineForecastService,
    _clamp,
    _linear_slope,
    _ols_coef,
    _blend,
)
from app.schemas.forecast import ForecastPoint


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_history(
    days: int,
    base_occ: float = 72.0,
    weekend_bump: float = 8.0,
) -> list[tuple[date, float]]:
    """Generate synthetic history with deterministic day-of-week pattern."""
    start = date(2024, 1, 1)
    result = []
    for i in range(days):
        d = start + timedelta(days=i)
        occ = base_occ + (weekend_bump if d.weekday() >= 5 else 0.0)
        result.append((d, occ))
    return result


@pytest.fixture
def svc() -> SeasonalBaselineForecastService:
    return SeasonalBaselineForecastService()


@pytest.fixture
def history_90() -> list[tuple[date, float]]:
    return _make_history(90)


@pytest.fixture
def history_14() -> list[tuple[date, float]]:
    return _make_history(14)


# ── Model metadata ────────────────────────────────────────────────────────────

def test_model_name(svc: SeasonalBaselineForecastService) -> None:
    assert svc.model_name == "Seasonal Baseline"


def test_min_history_days(svc: SeasonalBaselineForecastService) -> None:
    assert svc.min_history_days == 14


# ── Normal forecasting ────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_forecast_returns_correct_horizon(
    svc: SeasonalBaselineForecastService,
    history_90: list[tuple[date, float]],
) -> None:
    origin = history_90[-1][0]
    result = await svc.forecast("h1", history_90, horizon=14, origin=origin)
    assert len(result) == 14


@pytest.mark.anyio
async def test_forecast_dates_are_sequential(
    svc: SeasonalBaselineForecastService,
    history_90: list[tuple[date, float]],
) -> None:
    origin = history_90[-1][0]
    result = await svc.forecast("h1", history_90, horizon=7, origin=origin)
    for i, point in enumerate(result):
        assert point.forecast_date == origin + timedelta(days=i + 1)


@pytest.mark.anyio
async def test_forecast_first_date_is_origin_plus_one(
    svc: SeasonalBaselineForecastService,
    history_90: list[tuple[date, float]],
) -> None:
    origin = history_90[-1][0]
    result = await svc.forecast("h1", history_90, horizon=14, origin=origin)
    assert result[0].forecast_date == origin + timedelta(days=1)


@pytest.mark.anyio
async def test_forecast_last_date_matches_horizon(
    svc: SeasonalBaselineForecastService,
    history_90: list[tuple[date, float]],
) -> None:
    horizon = 14
    origin = history_90[-1][0]
    result = await svc.forecast("h1", history_90, horizon=horizon, origin=origin)
    assert result[-1].forecast_date == origin + timedelta(days=horizon)


@pytest.mark.anyio
async def test_custom_horizon(
    svc: SeasonalBaselineForecastService,
    history_90: list[tuple[date, float]],
) -> None:
    for horizon in (1, 7, 30, 90):
        origin = history_90[-1][0]
        result = await svc.forecast("h1", history_90, horizon=horizon, origin=origin)
        assert len(result) == horizon


# ── Occupancy bounds ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_occupancy_never_below_zero(
    svc: SeasonalBaselineForecastService,
    history_90: list[tuple[date, float]],
) -> None:
    # Use near-zero occupancy history
    low_history = [(d, 2.0) for d, _ in history_90]
    origin = low_history[-1][0]
    result = await svc.forecast("h1", low_history, horizon=14, origin=origin)
    for point in result:
        assert point.occupancy_pct >= 0.0
        assert point.lower_bound >= 0.0
        assert point.upper_bound >= 0.0


@pytest.mark.anyio
async def test_occupancy_never_above_100(
    svc: SeasonalBaselineForecastService,
    history_90: list[tuple[date, float]],
) -> None:
    # Use near-full occupancy history
    full_history = [(d, 98.0) for d, _ in history_90]
    origin = full_history[-1][0]
    result = await svc.forecast("h1", full_history, horizon=14, origin=origin)
    for point in result:
        assert point.occupancy_pct <= 100.0
        assert point.lower_bound <= 100.0
        assert point.upper_bound <= 100.0


@pytest.mark.anyio
async def test_lower_bound_lte_point_forecast(
    svc: SeasonalBaselineForecastService,
    history_90: list[tuple[date, float]],
) -> None:
    origin = history_90[-1][0]
    result = await svc.forecast("h1", history_90, horizon=14, origin=origin)
    for point in result:
        assert point.lower_bound <= point.occupancy_pct


@pytest.mark.anyio
async def test_upper_bound_gte_point_forecast(
    svc: SeasonalBaselineForecastService,
    history_90: list[tuple[date, float]],
) -> None:
    origin = history_90[-1][0]
    result = await svc.forecast("h1", history_90, horizon=14, origin=origin)
    for point in result:
        assert point.upper_bound >= point.occupancy_pct


# ── Confidence interval widens with horizon ───────────────────────────────────

@pytest.mark.anyio
async def test_confidence_interval_widens_with_horizon(
    svc: SeasonalBaselineForecastService,
    history_90: list[tuple[date, float]],
) -> None:
    """
    The final interval must be wider than the initial interval.
    We test overall growth rather than strict monotonicity because
    day-of-week occupancy variance can cause individual adjacent days
    to narrow slightly before the sqrt(h) growth dominates.
    """
    origin = history_90[-1][0]
    result = await svc.forecast("h1", history_90, horizon=14, origin=origin)
    widths = [p.upper_bound - p.lower_bound for p in result]
    assert widths[-1] > widths[0], (
        f"Expected final interval ({widths[-1]:.2f}) > initial ({widths[0]:.2f})"
    )


# ── Insufficient history ──────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_raises_on_insufficient_history(
    svc: SeasonalBaselineForecastService,
) -> None:
    short_history = _make_history(13)  # one below minimum
    origin = short_history[-1][0]
    with pytest.raises(ValueError, match="Insufficient history"):
        await svc.forecast("h1", short_history, horizon=14, origin=origin)


@pytest.mark.anyio
async def test_minimum_history_exactly_accepted(
    svc: SeasonalBaselineForecastService,
    history_14: list[tuple[date, float]],
) -> None:
    origin = history_14[-1][0]
    result = await svc.forecast("h1", history_14, horizon=7, origin=origin)
    assert len(result) == 7


# ── Helper function unit tests ────────────────────────────────────────────────

def test_clamp_within_range() -> None:
    assert _clamp(50.0) == 50.0


def test_clamp_below_zero() -> None:
    assert _clamp(-5.0) == 0.0


def test_clamp_above_100() -> None:
    assert _clamp(105.0) == 100.0


def test_linear_slope_flat() -> None:
    assert _linear_slope([50.0] * 10) == pytest.approx(0.0, abs=1e-9)


def test_linear_slope_increasing() -> None:
    # y = i → slope = 1
    slope = _linear_slope(list(range(10)))
    assert slope == pytest.approx(1.0, abs=1e-9)


def test_linear_slope_decreasing() -> None:
    slope = _linear_slope(list(range(10, 0, -1)))
    assert slope == pytest.approx(-1.0, abs=1e-9)


def test_linear_slope_single_value() -> None:
    assert _linear_slope([42.0]) == 0.0


def test_ols_coef_exact() -> None:
    # y = 2x → coef should be 2
    x = [1.0, 2.0, 3.0]
    y = [2.0, 4.0, 6.0]
    assert _ols_coef(x, y) == pytest.approx(2.0, abs=1e-9)


def test_blend_weights_sum_to_one() -> None:
    from app.services.forecasting.seasonal_baseline import _WEIGHTS
    total = sum(_WEIGHTS.values())
    assert total == pytest.approx(1.0, abs=1e-9)


# ── ForecastPoint schema validation ───────────────────────────────────────────

def test_forecast_point_rejects_out_of_range() -> None:
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        ForecastPoint(
            forecast_date=date.today(),
            occupancy_pct=110.0,  # invalid
            lower_bound=0.0,
            upper_bound=100.0,
        )
