"""
Seasonal Baseline Forecast Service
===================================
A lightweight, dependency-free occupancy forecasting implementation that
combines three signals:

    forecast = w_dow  * dow_avg
             + w_trend * trend_component
             + w_season * seasonal_component

Where:
  dow_avg          — mean occupancy for the same day-of-week over history
  trend_component  — linear slope estimated from the last 28 days
  seasonal_component — sinusoidal annual cycle fitted to all history

Confidence intervals are derived from the standard deviation of residuals
between the fitted in-sample predictions and the observed values, widened
by sqrt(h) to reflect forecast uncertainty growing with horizon.

This implementation is intentionally stdlib-only (no numpy/scipy) so that
it adds no new dependencies to the project while remaining fully replaceable
via the ForecastService ABC.
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import date, timedelta
from statistics import mean, stdev
from typing import Final

from app.schemas.forecast import ForecastPoint
from app.services.forecasting.base import ForecastService

logger = logging.getLogger(__name__)

# ── Tuning constants ──────────────────────────────────────────────────────────
_WEIGHTS: Final = {
    "dow": 0.45,      # day-of-week historical average
    "trend": 0.30,    # recent 28-day linear trend
    "seasonal": 0.25, # annual sinusoidal seasonality
}
_TREND_WINDOW: Final = 28        # days used for trend regression
_CONFIDENCE_Z: Final = 1.28      # ≈80 % confidence interval (z-score)
_MIN_HISTORY: Final = 14         # minimum required observations


class SeasonalBaselineForecastService(ForecastService):
    """
    Pluggable baseline implementation of ForecastService.

    Replace this with ``TimesFMForecastService`` (or any other subclass) in
    ``app/core/dependencies.py`` – the endpoint, schema, and frontend are
    unaffected.
    """

    model_name: str = "Seasonal Baseline"
    min_history_days: int = _MIN_HISTORY

    async def forecast(
        self,
        hotel_id: str,
        history: list[tuple[date, float]],
        horizon: int,
        origin: date,
    ) -> list[ForecastPoint]:
        if len(history) < _MIN_HISTORY:
            raise ValueError(
                f"Insufficient history: need ≥ {_MIN_HISTORY} days, "
                f"got {len(history)} for hotel {hotel_id}"
            )

        occupancies = [occ for _, occ in history]
        dates = [d for d, _ in history]

        # ── Component 1: day-of-week averages ─────────────────────────────
        dow_buckets: dict[int, list[float]] = defaultdict(list)
        for d, occ in history:
            dow_buckets[d.weekday()].append(occ)
        dow_avg: dict[int, float] = {
            dow: mean(vals) for dow, vals in dow_buckets.items()
        }
        global_mean = mean(occupancies)
        # Fill any missing weekday with the global mean
        for dow in range(7):
            dow_avg.setdefault(dow, global_mean)

        # ── Component 2: recent linear trend ──────────────────────────────
        trend_window = occupancies[-_TREND_WINDOW:]
        slope = _linear_slope(trend_window)  # occupancy % change per day
        trend_base = mean(trend_window)

        # ── Component 3: annual seasonal component ─────────────────────────
        # Fit a single sinusoid: A * sin(2π * day_of_year / 365 + φ)
        # We approximate amplitude and phase from the data.
        sin_vals, cos_vals, occ_vals = [], [], []
        for d, occ in history:
            angle = 2 * math.pi * d.timetuple().tm_yday / 365
            sin_vals.append(math.sin(angle))
            cos_vals.append(math.cos(angle))
            occ_vals.append(occ)
        sin_coef = _ols_coef(sin_vals, occ_vals)
        cos_coef = _ols_coef(cos_vals, occ_vals)

        # ── In-sample residuals for confidence interval ────────────────────
        residuals: list[float] = []
        for i, (d, actual) in enumerate(history):
            fitted = _blend(
                dow_avg=dow_avg[d.weekday()],
                trend_val=trend_base + slope * (i - len(history) + 1),
                seasonal_val=_seasonal(d, sin_coef, cos_coef, global_mean),
            )
            residuals.append(actual - fitted)

        residual_std = stdev(residuals) if len(residuals) > 1 else 5.0

        # ── Generate horizon forecasts ─────────────────────────────────────
        points: list[ForecastPoint] = []
        for h in range(1, horizon + 1):
            fdate = origin + timedelta(days=h)
            trend_val = trend_base + slope * h
            seasonal_val = _seasonal(fdate, sin_coef, cos_coef, global_mean)
            point = _blend(
                dow_avg=dow_avg[fdate.weekday()],
                trend_val=trend_val,
                seasonal_val=seasonal_val,
            )
            # Confidence interval widens with sqrt of horizon
            margin = _CONFIDENCE_Z * residual_std * math.sqrt(h)
            points.append(
                ForecastPoint(
                    forecast_date=fdate,
                    occupancy_pct=_clamp(point),
                    lower_bound=_clamp(point - margin),
                    upper_bound=_clamp(point + margin),
                )
            )

        logger.debug(
            "hotel=%s horizon=%d origin=%s model=%s",
            hotel_id, horizon, origin, self.model_name,
        )
        return points


# ── Pure helper functions (no side effects) ───────────────────────────────────

def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """Clamp occupancy to [0, 100]."""
    return max(lo, min(hi, round(value, 2)))


def _blend(dow_avg: float, trend_val: float, seasonal_val: float) -> float:
    return (
        _WEIGHTS["dow"] * dow_avg
        + _WEIGHTS["trend"] * trend_val
        + _WEIGHTS["seasonal"] * seasonal_val
    )


def _seasonal(d: date, sin_coef: float, cos_coef: float, intercept: float) -> float:
    """Evaluate the fitted sinusoidal seasonal component for a given date."""
    angle = 2 * math.pi * d.timetuple().tm_yday / 365
    return intercept + sin_coef * math.sin(angle) + cos_coef * math.cos(angle)


def _linear_slope(values: list[float]) -> float:
    """Ordinary-least-squares slope of a 1-D sequence (index = x, value = y)."""
    n = len(values)
    if n < 2:
        return 0.0
    x_bar = (n - 1) / 2
    y_bar = mean(values)
    num = sum((i - x_bar) * (v - y_bar) for i, v in enumerate(values))
    den = sum((i - x_bar) ** 2 for i in range(n))
    return num / den if den != 0 else 0.0


def _ols_coef(x: list[float], y: list[float]) -> float:
    """OLS coefficient for a single predictor (no intercept)."""
    dot = sum(xi * yi for xi, yi in zip(x, y))
    sq  = sum(xi * xi for xi in x)
    return dot / sq if sq != 0 else 0.0
