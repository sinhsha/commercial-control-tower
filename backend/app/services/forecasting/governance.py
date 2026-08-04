"""
ForecastGovernanceService
=========================
Validates a list of ForecastPoints against business rules.  On any
rule failure, the service falls back to SeasonalBaselineForecastService
and returns a GovernanceResult with fallback_used=True.

Rules:
  1. Occupancy values in [0, 100]
  2. No missing dates in the sequence (origin+1 through origin+horizon)
  3. No duplicate dates
  4. Day-over-day absolute jump ≤ max_jump_pp (default 30 pp)
  5. lower_bound ≤ occupancy_pct ≤ upper_bound
  6. Minimum history available (default 14 days)
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Literal

from app.schemas.forecast import ForecastPoint
from app.schemas.forecasting import GovernanceResult
from app.services.forecasting.base import ForecastService
from app.services.forecasting.seasonal_baseline import SeasonalBaselineForecastService

logger = logging.getLogger(__name__)

ValidationStatus = Literal["passed", "warning", "failed"]


class ForecastGovernanceService:
    """Validates forecasts and falls back to SeasonalBaseline on failure."""

    def __init__(
        self,
        fallback_svc: ForecastService | None = None,
        max_jump_pp: float = 30.0,
        min_history_days: int = 14,
    ) -> None:
        self._fallback = fallback_svc or SeasonalBaselineForecastService()
        self.max_jump_pp = max_jump_pp
        self.min_history_days = min_history_days

    async def validate_and_govern(
        self,
        hotel_id: str,
        forecast_points: list[ForecastPoint],
        history: list[tuple[date, float]],
        origin: date,
        horizon: int,
    ) -> tuple[list[ForecastPoint], GovernanceResult]:
        """
        Validate `forecast_points`.  If validation fails, re-run forecast
        with the fallback service and return its output.

        Returns (final_points, governance_result).
        """
        warnings: list[str] = []
        status: ValidationStatus = "passed"

        # Rule 6: minimum history
        if len(history) < self.min_history_days:
            msg = (
                f"Insufficient history: need ≥ {self.min_history_days} days, "
                f"got {len(history)}"
            )
            warnings.append(msg)
            status = "failed"
            return await self._do_fallback(
                hotel_id, history, origin, horizon, warnings, msg
            )

        if not forecast_points:
            msg = "Forecast is empty"
            warnings.append(msg)
            status = "failed"
            return await self._do_fallback(
                hotel_id, history, origin, horizon, warnings, msg
            )

        # Rule 3: duplicate dates
        seen_dates: set[date] = set()
        duplicates: list[date] = []
        for fp in forecast_points:
            if fp.forecast_date in seen_dates:
                duplicates.append(fp.forecast_date)
            seen_dates.add(fp.forecast_date)
        if duplicates:
            msg = f"Duplicate forecast dates: {[str(d) for d in duplicates]}"
            warnings.append(msg)
            status = "failed"
            return await self._do_fallback(
                hotel_id, history, origin, horizon, warnings, msg
            )

        # Rule 2: missing dates
        expected = {origin + timedelta(days=h) for h in range(1, horizon + 1)}
        missing = expected - seen_dates
        if missing:
            msg = f"Missing forecast dates: {sorted(str(d) for d in missing)}"
            warnings.append(msg)
            status = "failed"
            return await self._do_fallback(
                hotel_id, history, origin, horizon, warnings, msg
            )

        # Rule 1 + 5: per-point checks
        for fp in forecast_points:
            if not (0.0 <= fp.occupancy_pct <= 100.0):
                msg = (
                    f"occupancy_pct {fp.occupancy_pct} out of [0,100] "
                    f"on {fp.forecast_date}"
                )
                warnings.append(msg)
                status = "failed"
                return await self._do_fallback(
                    hotel_id, history, origin, horizon, warnings, msg
                )
            if fp.lower_bound > fp.occupancy_pct:
                msg = (
                    f"lower_bound {fp.lower_bound} > occupancy_pct "
                    f"{fp.occupancy_pct} on {fp.forecast_date}"
                )
                warnings.append(msg)
                status = "failed"
                return await self._do_fallback(
                    hotel_id, history, origin, horizon, warnings, msg
                )
            if fp.upper_bound < fp.occupancy_pct:
                msg = (
                    f"upper_bound {fp.upper_bound} < occupancy_pct "
                    f"{fp.occupancy_pct} on {fp.forecast_date}"
                )
                warnings.append(msg)
                status = "failed"
                return await self._do_fallback(
                    hotel_id, history, origin, horizon, warnings, msg
                )

        # Rule 4: day-over-day jump
        prev_occ: float | None = history[-1][1] if history else None
        for fp in sorted(forecast_points, key=lambda p: p.forecast_date):
            if prev_occ is not None:
                jump = abs(fp.occupancy_pct - prev_occ)
                if jump > self.max_jump_pp:
                    msg = (
                        f"Day-over-day jump {jump:.1f}pp > threshold "
                        f"{self.max_jump_pp}pp on {fp.forecast_date}"
                    )
                    warnings.append(msg)
                    status = "warning"  # warn but don't fail
            prev_occ = fp.occupancy_pct

        result = GovernanceResult(
            validation_status=status,
            warnings=warnings,
            fallback_used=False,
        )
        return forecast_points, result

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _do_fallback(
        self,
        hotel_id: str,
        history: list[tuple[date, float]],
        origin: date,
        horizon: int,
        warnings: list[str],
        reason: str,
    ) -> tuple[list[ForecastPoint], GovernanceResult]:
        logger.warning(
            "Governance fallback triggered for hotel=%s reason=%s",
            hotel_id, reason,
        )
        result = GovernanceResult(
            validation_status="failed",
            warnings=warnings,
            fallback_used=True,
            fallback_reason=reason,
        )
        try:
            fallback_points = await self._fallback.forecast(
                hotel_id=hotel_id,
                history=history,
                horizon=horizon,
                origin=origin,
            )
        except ValueError:
            # History also too short for fallback — return empty forecast
            logger.warning(
                "Fallback forecast also failed for hotel=%s (insufficient history)",
                hotel_id,
            )
            return [], result
        return fallback_points, result
