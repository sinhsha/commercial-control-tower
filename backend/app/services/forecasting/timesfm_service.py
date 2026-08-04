"""
TimesFMForecastService
======================
Adapter implementing the ForecastService ABC for Google TimesFM 2.x
(google/timesfm-2.5-200m-pytorch via HuggingFace).

TimesFM is NOT a hard dependency.  This module lazy-loads the library and
gracefully degrades to SeasonalBaselineForecastService on:
  • ImportError / ModuleNotFoundError  — torch or timesfm not installed
  • asyncio.TimeoutError               — inference exceeded timeout_seconds
  • Any unexpected exception           — captured and logged
  • Model not yet downloaded           — first run downloads ~800 MB

API used (timesfm 2.x):
    model = TimesFM_2p5_200M_torch.from_pretrained(repo_id)
    point_forecasts, quantile_forecasts = model.forecast(horizon, [context])
      point_forecasts:    np.ndarray shape (1, horizon)     — median point estimate
      quantile_forecasts: np.ndarray shape (1, horizon, 9)  — q0.1..q0.9

The returned list[ForecastPoint] is identical in shape regardless of
which path ran, so callers never need to distinguish.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from app.schemas.forecast import ForecastPoint
from app.services.forecasting.base import ForecastService
from app.services.forecasting.seasonal_baseline import SeasonalBaselineForecastService

logger = logging.getLogger(__name__)

# HuggingFace repo for TimesFM 2.5 PyTorch weights
_DEFAULT_REPO_ID = "google/timesfm-2.5-200m-pytorch"


class TimesFMForecastService(ForecastService):
    """
    TimesFM 2.x adapter with automatic fallback to SeasonalBaseline.

    Attributes
    ----------
    is_fallback : bool
        True if the last forecast() call used the fallback.
    fallback_reason : str | None
        Human-readable reason for the last fallback, or None if TimesFM ran.
    """

    model_name: str = "TimesFM"
    min_history_days: int = 14

    def __init__(
        self,
        timeout_seconds: float = 10.0,
        device: str = "cpu",
        repo_id: str = _DEFAULT_REPO_ID,
        context_length: int = 512,
        fallback_svc: ForecastService | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.device = device
        self.repo_id = repo_id
        self.context_length = context_length
        self._fallback = fallback_svc or SeasonalBaselineForecastService()

        # Per-call state
        self.is_fallback: bool = False
        self.fallback_reason: str | None = None

        # Lazy-loaded model singleton (loaded on first forecast call)
        self._model = None
        self._available = self._check_available()

    # ── Availability check ────────────────────────────────────────────────────

    def _check_available(self) -> bool:
        """True only when both timesfm and torch packages are importable."""
        try:
            import importlib.util
            timesfm_ok = importlib.util.find_spec("timesfm") is not None
            torch_ok = importlib.util.find_spec("torch") is not None
            return timesfm_ok and torch_ok
        except Exception:
            return False

    # ── Public forecast interface ─────────────────────────────────────────────

    async def forecast(
        self,
        hotel_id: str,
        history: list[tuple[date, float]],
        horizon: int,
        origin: date,
    ) -> list[ForecastPoint]:
        if not self._available:
            self.is_fallback = True
            self.fallback_reason = "timesfm or torch library not installed"
            logger.warning(
                "TimesFM not available for hotel=%s — falling back to %s",
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
                "TimesFM timeout for hotel=%s — falling back to %s",
                hotel_id, self._fallback.model_name,
            )
            return await self._fallback.forecast(hotel_id, history, horizon, origin)
        except Exception as exc:
            self.is_fallback = True
            self.fallback_reason = f"TimesFM error: {exc}"
            logger.exception(
                "TimesFM failed for hotel=%s — falling back: %s", hotel_id, exc
            )
            return await self._fallback.forecast(hotel_id, history, horizon, origin)

    # ── Async wrapper ─────────────────────────────────────────────────────────

    async def _run_timesfm(
        self,
        hotel_id: str,
        history: list[tuple[date, float]],
        horizon: int,
        origin: date,
    ) -> list[ForecastPoint]:
        """Offloads blocking model inference to a thread executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._sync_inference,
            hotel_id, history, horizon, origin,
        )

    # ── Blocking inference (runs in thread) ───────────────────────────────────

    def _load_model(self):
        """Lazy-load the TimesFM 2.x model (downloads weights on first call)."""
        if self._model is not None:
            return
        from timesfm import TimesFM_2p5_200M_torch  # type: ignore[import]
        logger.info("Loading TimesFM 2.5 weights from %s …", self.repo_id)
        self._model = TimesFM_2p5_200M_torch.from_pretrained(self.repo_id)
        logger.info("TimesFM 2.5 model loaded.")

    def _sync_inference(
        self,
        hotel_id: str,
        history: list[tuple[date, float]],
        horizon: int,
        origin: date,
    ) -> list[ForecastPoint]:
        """
        Blocking TimesFM 2.x inference.

        TimesFM 2.x API:
            point_fc, quantile_fc = model.forecast(horizon, [context_array])
            point_fc      shape: (1, horizon)
            quantile_fc   shape: (1, horizon, 9)  — q0.1 … q0.9
        """
        import numpy as np

        self._load_model()

        # Build occupancy context, truncated to context_length
        occupancies = [float(occ) for _, occ in history]
        context = np.array(occupancies[-self.context_length:], dtype=np.float32)

        # Run inference — model.forecast returns numpy arrays
        point_forecasts, quantile_forecasts = self._model.forecast(
            horizon=horizon,
            inputs=[context],
        )

        # point_forecasts: (1, horizon) → take first batch
        raw = point_forecasts[0]  # shape: (horizon,)

        # q10 = quantile index 0, q90 = quantile index 8
        q10 = quantile_forecasts[0, :, 0]   # shape: (horizon,)
        q90 = quantile_forecasts[0, :, 8]   # shape: (horizon,)

        def _clamp(v: float) -> float:
            return float(max(0.0, min(100.0, round(v, 2))))

        points: list[ForecastPoint] = []
        for h in range(1, horizon + 1):
            idx = h - 1
            occ = _clamp(raw[idx]) if idx < len(raw) else _clamp(occupancies[-1])
            lo  = _clamp(q10[idx]) if idx < len(q10) else _clamp(occ * 0.9)
            hi  = _clamp(q90[idx]) if idx < len(q90) else _clamp(occ * 1.1)
            points.append(ForecastPoint(
                forecast_date=origin + timedelta(days=h),
                occupancy_pct=occ,
                lower_bound=min(lo, occ),
                upper_bound=max(hi, occ),
            ))

        self.is_fallback = False
        self.fallback_reason = None
        return points
