"""
TimesFMForecastService
======================
Adapter implementing the ForecastService ABC for Google TimesFM.

TimesFM is NOT a hard dependency of this project.  This module attempts
``import timesfm`` at call-time and, on ImportError or timeout, gracefully
degrades to SeasonalBaselineForecastService.

Fallback triggers:
  • ImportError / ModuleNotFoundError  — library not installed
  • asyncio.TimeoutError               — inference exceeded timeout_seconds
  • Any unexpected exception           — captured and logged

The returned list[ForecastPoint] is identical in shape regardless of
which path ran, so callers never need to distinguish.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date

from app.schemas.forecast import ForecastPoint
from app.services.forecasting.base import ForecastService
from app.services.forecasting.seasonal_baseline import SeasonalBaselineForecastService

logger = logging.getLogger(__name__)


class TimesFMForecastService(ForecastService):
    """
    TimesFM adapter with automatic fallback to SeasonalBaseline.

    Attributes
    ----------
    is_fallback : bool
        True if the last forecast() call used the fallback.
    fallback_reason : str | None
        Human-readable reason for the last fallback, or None.
    """

    model_name: str = "TimesFM"
    min_history_days: int = 14

    def __init__(
        self,
        timeout_seconds: float = 10.0,
        device: str = "cpu",
        model_name_hf: str = "google/timesfm-1.0-200m",
        context_length: int = 512,
        prediction_length: int = 96,
        fallback_svc: ForecastService | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.device = device
        self.model_name_hf = model_name_hf
        self.context_length = context_length
        self.prediction_length = prediction_length
        self._fallback = fallback_svc or SeasonalBaselineForecastService()

        # Per-call state (set during forecast())
        self.is_fallback: bool = False
        self.fallback_reason: str | None = None

        # Test if the library is available
        self._available = self._check_available()

    def _check_available(self) -> bool:
        try:
            import importlib.util
            spec = importlib.util.find_spec("timesfm")
            return spec is not None
        except Exception:
            return False

    async def forecast(
        self,
        hotel_id: str,
        history: list[tuple[date, float]],
        horizon: int,
        origin: date,
    ) -> list[ForecastPoint]:
        if not self._available:
            self.is_fallback = True
            self.fallback_reason = "timesfm library not installed"
            logger.warning(
                "TimesFM not available for hotel=%s, falling back to %s",
                hotel_id, self._fallback.model_name,
            )
            return await self._fallback.forecast(hotel_id, history, horizon, origin)

        try:
            return await asyncio.wait_for(
                self._run_timesfm(hotel_id, history, horizon, origin),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            self.is_fallback = True
            self.fallback_reason = (
                f"TimesFM inference exceeded {self.timeout_seconds}s timeout"
            )
            logger.warning(
                "TimesFM timeout for hotel=%s, falling back to %s",
                hotel_id, self._fallback.model_name,
            )
            return await self._fallback.forecast(hotel_id, history, horizon, origin)
        except Exception as exc:
            self.is_fallback = True
            self.fallback_reason = f"TimesFM error: {exc}"
            logger.exception(
                "TimesFM failed for hotel=%s, falling back: %s", hotel_id, exc
            )
            return await self._fallback.forecast(hotel_id, history, horizon, origin)

    async def _run_timesfm(
        self,
        hotel_id: str,
        history: list[tuple[date, float]],
        horizon: int,
        origin: date,
    ) -> list[ForecastPoint]:
        """
        Actual TimesFM inference path.
        Only reached when ``timesfm`` is importable.
        Runs in a thread executor to avoid blocking the event loop.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._sync_timesfm_inference,
            hotel_id, history, horizon, origin,
        )

    def _sync_timesfm_inference(
        self,
        hotel_id: str,
        history: list[tuple[date, float]],
        horizon: int,
        origin: date,
    ) -> list[ForecastPoint]:
        """Blocking inference — called from thread executor."""
        import timesfm  # type: ignore[import]
        import math
        from datetime import timedelta

        occupancies = [float(occ) for _, occ in history]
        context = occupancies[-self.context_length:]

        tfm = timesfm.TimesFm(
            hparams=timesfm.TimesFmHparams(
                backend=self.device,
                per_core_batch_size=1,
                horizon_len=min(horizon, self.prediction_length),
            ),
            checkpoint=timesfm.TimesFmCheckpoint(
                huggingface_repo_id=self.model_name_hf
            ),
        )

        point_forecasts, experimental_quantile_forecasts, _ = tfm.forecast(
            [context],
            freq=[0],
        )

        raw = point_forecasts[0][:horizon]
        q10 = experimental_quantile_forecasts[0][:horizon, 0]  # ~10th percentile
        q90 = experimental_quantile_forecasts[0][:horizon, -1] # ~90th percentile

        def _clamp(v: float) -> float:
            return max(0.0, min(100.0, round(v, 2)))

        points: list[ForecastPoint] = []
        for h in range(1, horizon + 1):
            idx = h - 1
            occ = _clamp(raw[idx]) if idx < len(raw) else _clamp(occupancies[-1])
            lo = _clamp(q10[idx]) if idx < len(q10) else _clamp(occ * 0.9)
            hi = _clamp(q90[idx]) if idx < len(q90) else _clamp(occ * 1.1)
            points.append(ForecastPoint(
                forecast_date=origin + timedelta(days=h),
                occupancy_pct=occ,
                lower_bound=min(lo, occ),
                upper_bound=max(hi, occ),
            ))

        self.is_fallback = False
        self.fallback_reason = None
        return points
