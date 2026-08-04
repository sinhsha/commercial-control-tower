"""
ForecastManagerService
======================
Orchestrates the full forecast pipeline:

  1. Model selection (config-driven: baseline | timesfm | auto)
  2. Run forecast
  3. Governance validation
  4. Return ManagedForecastResult with full metadata

Config env var: FORECAST_PROVIDER=baseline|timesfm|auto
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import date, datetime, timezone

from app.schemas.forecast import ForecastPoint
from app.schemas.forecasting import EvaluationResult, ManagedForecastResult
from app.services.forecasting.auto_selector import AutoModelSelector
from app.services.forecasting.base import ForecastService
from app.services.forecasting.evaluation import ForecastEvaluationService
from app.services.forecasting.governance import ForecastGovernanceService
from app.services.forecasting.model_registry import ForecastModelRegistry
from app.services.forecasting.seasonal_baseline import SeasonalBaselineForecastService
from app.services.forecasting.timesfm_service import TimesFMForecastService

logger = logging.getLogger(__name__)


class ForecastManagerService:
    """
    Orchestrator that selects a model, runs the forecast, validates it
    via governance, and returns a fully-enriched ManagedForecastResult.
    """

    def __init__(
        self,
        provider: str = "baseline",
        registry: ForecastModelRegistry | None = None,
        baseline_svc: ForecastService | None = None,
        timesfm_svc: ForecastService | None = None,
        governance_svc: ForecastGovernanceService | None = None,
        auto_selector: AutoModelSelector | None = None,
        eval_svc: ForecastEvaluationService | None = None,
    ) -> None:
        self._provider = provider.lower()
        self._registry = registry
        self._baseline = baseline_svc or SeasonalBaselineForecastService()
        self._timesfm = timesfm_svc or TimesFMForecastService()
        self._governance = governance_svc or ForecastGovernanceService()
        self._auto_selector = auto_selector
        self._eval_svc = eval_svc or ForecastEvaluationService(self._baseline)

        self._services: dict[str, ForecastService] = {
            "seasonal_baseline": self._baseline,
            "timesfm": self._timesfm,
        }

    async def forecast(
        self,
        hotel_id: str,
        history: list[tuple[date, float]],
        horizon: int,
        origin: date,
    ) -> ManagedForecastResult:
        """
        Run the full managed forecast pipeline.

        Returns
        -------
        ManagedForecastResult
            Enriched forecast with metadata, validation status, and metrics.
        """
        forecast_id = str(uuid.uuid4())
        t_start = time.perf_counter()

        # ── 1. Select model ──────────────────────────────────────────────────
        model_id, selection_reason = await self._select_model(hotel_id, history)
        svc = self._services.get(model_id, self._baseline)
        device = getattr(svc, "device", "cpu")
        model_version = "1.0.0"

        # ── 2. Run forecast ──────────────────────────────────────────────────
        try:
            raw_points: list[ForecastPoint] = await svc.forecast(
                hotel_id=hotel_id,
                history=history,
                horizon=horizon,
                origin=origin,
            )
        except Exception as exc:
            logger.warning(
                "Manager: primary forecast failed for hotel=%s model=%s: %s; "
                "falling back to baseline",
                hotel_id, model_id, exc,
            )
            model_id = "seasonal_baseline"
            svc = self._baseline
            raw_points = await svc.forecast(
                hotel_id=hotel_id,
                history=history,
                horizon=horizon,
                origin=origin,
            )

        # ── 3. Governance ────────────────────────────────────────────────────
        final_points, gov_result = await self._governance.validate_and_govern(
            hotel_id=hotel_id,
            forecast_points=raw_points,
            history=history,
            origin=origin,
            horizon=horizon,
        )

        # If governance used fallback, update model_id
        if gov_result.fallback_used:
            model_id = "seasonal_baseline"
            svc = self._baseline

        runtime_ms = (time.perf_counter() - t_start) * 1000.0

        # ── 4. Quick evaluation metrics (best-effort) ────────────────────────
        eval_result: EvaluationResult | None = None
        try:
            eval_result = await self._eval_svc.evaluate(
                hotel_id=hotel_id,
                history=history,
                window="last_30",
                model_id=model_id,
            )
        except Exception:
            pass  # metrics are optional

        # Confidence score: simple heuristic from evaluation
        confidence_score = _derive_confidence(eval_result)

        # ── 5. Serialise forecast points ─────────────────────────────────────
        forecast_dicts = [
            {
                "forecast_date": str(fp.forecast_date),
                "occupancy_pct": fp.occupancy_pct,
                "lower_bound": fp.lower_bound,
                "upper_bound": fp.upper_bound,
            }
            for fp in final_points
        ]

        return ManagedForecastResult(
            forecast_id=forecast_id,
            hotel_id=hotel_id,
            model_used=model_id,
            model_version=model_version,
            generated_at=datetime.now(timezone.utc),
            runtime_ms=round(runtime_ms, 2),
            device=device,
            training_context_days=len(history),
            prediction_horizon=horizon,
            validation_status=gov_result.validation_status,
            fallback_used=gov_result.fallback_used,
            fallback_reason=gov_result.fallback_reason,
            confidence_score=confidence_score,
            evaluation_metrics=eval_result,
            warnings=gov_result.warnings,
            forecast=forecast_dicts,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _select_model(
        self,
        hotel_id: str,
        history: list[tuple[date, float]],
    ) -> tuple[str, str]:
        if self._provider == "timesfm":
            return "timesfm", "configured provider=timesfm"
        if self._provider == "auto" and self._auto_selector is not None:
            return await self._auto_selector.select(hotel_id, history)
        return "seasonal_baseline", "configured provider=baseline"


def _derive_confidence(eval_result: EvaluationResult | None) -> float:
    """Map WAPE to a confidence score in [0, 1]."""
    if eval_result is None:
        return 0.7
    # WAPE=0 → 1.0, WAPE=50+ → 0.0
    return max(0.0, min(1.0, round(1.0 - eval_result.wape / 50.0, 3)))
