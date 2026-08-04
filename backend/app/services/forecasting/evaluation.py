"""
ForecastEvaluationService
=========================
Walk-forward validation: split last N days of history, generate forecasts
on prior window, compare against actuals.

Metrics computed:
  MAE    — Mean Absolute Error
  RMSE   — Root Mean Squared Error
  MAPE   — Mean Absolute Percentage Error
  WAPE   — Weighted Absolute Percentage Error
  Bias   — mean(predicted – actual)
  Mean Error — same as Bias (explicit alias)
  Coverage — % of actuals within confidence interval
  runtime_ms — inference wall-clock time
"""
from __future__ import annotations

import logging
import math
import time
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from app.schemas.forecast import ForecastPoint
from app.schemas.forecasting import BacktestPoint, BacktestResult, EvaluationResult
from app.services.forecasting.base import ForecastService

logger = logging.getLogger(__name__)

EvaluationWindow = Literal["last_30", "last_60", "last_90"]

_WINDOW_DAYS: dict[str, int] = {
    "last_30": 30,
    "last_60": 60,
    "last_90": 90,
}


def _mae(actuals: list[float], predicted: list[float]) -> float:
    if not actuals:
        return 0.0
    return sum(abs(a - p) for a, p in zip(actuals, predicted)) / len(actuals)


def _rmse(actuals: list[float], predicted: list[float]) -> float:
    if not actuals:
        return 0.0
    return math.sqrt(sum((a - p) ** 2 for a, p in zip(actuals, predicted)) / len(actuals))


def _mape(actuals: list[float], predicted: list[float]) -> float:
    """Mean Absolute Percentage Error — skips zero actuals to avoid div/0."""
    pairs = [(a, p) for a, p in zip(actuals, predicted) if a != 0.0]
    if not pairs:
        return 0.0
    return 100.0 * sum(abs(a - p) / abs(a) for a, p in pairs) / len(pairs)


def _wape(actuals: list[float], predicted: list[float]) -> float:
    """Weighted Absolute Percentage Error = sum|e| / sum|actual|."""
    denom = sum(abs(a) for a in actuals)
    if denom == 0.0:
        return 0.0
    return 100.0 * sum(abs(a - p) for a, p in zip(actuals, predicted)) / denom


def _bias(actuals: list[float], predicted: list[float]) -> float:
    if not actuals:
        return 0.0
    return sum(p - a for a, p in zip(actuals, predicted)) / len(actuals)


def _coverage(
    actuals: list[float],
    lowers: list[float],
    uppers: list[float],
) -> float:
    """% of actuals within [lower, upper]."""
    if not actuals:
        return 0.0
    hits = sum(1 for a, lo, hi in zip(actuals, lowers, uppers) if lo <= a <= hi)
    return 100.0 * hits / len(actuals)


class ForecastEvaluationService:
    """Walk-forward evaluation of a ForecastService implementation."""

    def __init__(self, forecast_svc: ForecastService) -> None:
        self._svc = forecast_svc

    async def evaluate(
        self,
        hotel_id: str,
        history: list[tuple[date, float]],
        window: EvaluationWindow = "last_30",
        model_id: str = "seasonal_baseline",
    ) -> EvaluationResult:
        """
        Split the last `window_days` from `history` as a hold-out set,
        generate forecasts from the prior window, and compute metrics.
        """
        window_days = _WINDOW_DAYS.get(window, 30)
        min_required = self._svc.min_history_days + window_days

        if len(history) < min_required:
            # Not enough data — return zero metrics
            logger.warning(
                "Insufficient history for evaluation (hotel=%s, need=%d, got=%d)",
                hotel_id, min_required, len(history),
            )
            return EvaluationResult(
                model_id=model_id,
                model_name=self._svc.model_name,
                window=window,
                mae=0.0, rmse=0.0, mape=0.0, wape=0.0,
                bias=0.0, mean_error=0.0, coverage=0.0, runtime_ms=0.0,
                evaluated_at=datetime.now(timezone.utc),
            )

        train = history[:-window_days]
        hold_out = history[-window_days:]
        origin = train[-1][0]

        start_ms = time.perf_counter()
        forecast_points: list[ForecastPoint] = await self._svc.forecast(
            hotel_id=hotel_id,
            history=train,
            horizon=window_days,
            origin=origin,
        )
        runtime_ms = (time.perf_counter() - start_ms) * 1000.0

        actuals = [occ for _, occ in hold_out]
        predicted = [fp.occupancy_pct for fp in forecast_points]
        lowers = [fp.lower_bound for fp in forecast_points]
        uppers = [fp.upper_bound for fp in forecast_points]

        bias_val = _bias(actuals, predicted)

        return EvaluationResult(
            model_id=model_id,
            model_name=self._svc.model_name,
            window=window,
            mae=round(_mae(actuals, predicted), 4),
            rmse=round(_rmse(actuals, predicted), 4),
            mape=round(_mape(actuals, predicted), 4),
            wape=round(_wape(actuals, predicted), 4),
            bias=round(bias_val, 4),
            mean_error=round(bias_val, 4),
            coverage=round(_coverage(actuals, lowers, uppers), 2),
            runtime_ms=round(runtime_ms, 2),
            evaluated_at=datetime.now(timezone.utc),
        )

    async def backtest(
        self,
        hotel_id: str,
        history: list[tuple[date, float]],
        window: EvaluationWindow = "last_30",
        model_id: str = "seasonal_baseline",
    ) -> BacktestResult:
        """Return actuals vs predicted with residuals for each date."""
        window_days = _WINDOW_DAYS.get(window, 30)
        min_required = self._svc.min_history_days + window_days

        if len(history) < min_required:
            return BacktestResult(
                model_id=model_id,
                model_name=self._svc.model_name,
                window=window,
                points=[],
                mae=0.0, rmse=0.0, bias=0.0,
            )

        train = history[:-window_days]
        hold_out = history[-window_days:]
        origin = train[-1][0]

        forecast_points = await self._svc.forecast(
            hotel_id=hotel_id,
            history=train,
            horizon=window_days,
            origin=origin,
        )

        points: list[BacktestPoint] = []
        actuals_list: list[float] = []
        predicted_list: list[float] = []

        for (d, actual), fp in zip(hold_out, forecast_points):
            predicted = fp.occupancy_pct
            points.append(BacktestPoint(
                date=d,
                actual=round(actual, 2),
                predicted=round(predicted, 2),
                lower_bound=round(fp.lower_bound, 2),
                upper_bound=round(fp.upper_bound, 2),
                residual=round(predicted - actual, 2),
            ))
            actuals_list.append(actual)
            predicted_list.append(predicted)

        return BacktestResult(
            model_id=model_id,
            model_name=self._svc.model_name,
            window=window,
            points=points,
            mae=round(_mae(actuals_list, predicted_list), 4),
            rmse=round(_rmse(actuals_list, predicted_list), 4),
            bias=round(_bias(actuals_list, predicted_list), 4),
        )
