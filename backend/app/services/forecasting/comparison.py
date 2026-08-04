"""
ForecastComparisonService
=========================
Runs walk-forward evaluation for all active registered models and
returns side-by-side EvaluationResult objects plus a recommended model.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from app.schemas.forecasting import ComparisonResult, EvaluationResult
from app.services.forecasting.evaluation import ForecastEvaluationService, EvaluationWindow
from app.services.forecasting.model_registry import ForecastModelRegistry
from app.services.forecasting.seasonal_baseline import SeasonalBaselineForecastService

logger = logging.getLogger(__name__)


class ForecastComparisonService:
    """Runs evaluation for all registered active models and compares results."""

    def __init__(
        self,
        registry: ForecastModelRegistry,
        baseline_eval_svc: ForecastEvaluationService,
        timesfm_eval_svc: ForecastEvaluationService | None = None,
    ) -> None:
        self._registry = registry
        self._eval_svcs: dict[str, ForecastEvaluationService] = {
            "seasonal_baseline": baseline_eval_svc,
        }
        if timesfm_eval_svc is not None:
            self._eval_svcs["timesfm"] = timesfm_eval_svc

    async def compare(
        self,
        hotel_id: str,
        history: list[tuple[date, float]],
        window: EvaluationWindow = "last_30",
    ) -> ComparisonResult:
        results: list[EvaluationResult] = []

        for model in self._registry.list_active():
            eval_svc = self._eval_svcs.get(model.model_id)
            if eval_svc is None:
                # Use baseline as fallback evaluator for unknown active models
                eval_svc = self._eval_svcs["seasonal_baseline"]

            try:
                result = await eval_svc.evaluate(
                    hotel_id=hotel_id,
                    history=history,
                    window=window,
                    model_id=model.model_id,
                )
                results.append(result)
            except Exception as exc:
                logger.warning(
                    "Evaluation failed for model=%s hotel=%s: %s",
                    model.model_id, hotel_id, exc,
                )

        if not results:
            # Return empty comparison with baseline placeholder
            baseline = self._eval_svcs["seasonal_baseline"]
            results = [
                await baseline.evaluate(hotel_id, history, window, "seasonal_baseline")
            ]

        # Pick recommended: lowest WAPE → lowest |bias| → fastest runtime
        best = min(
            results,
            key=lambda r: (r.wape, abs(r.bias), r.runtime_ms),
        )

        return ComparisonResult(
            hotel_id=hotel_id,
            window=window,
            models=results,
            recommended_model_id=best.model_id,
            evaluated_at=datetime.now(timezone.utc),
        )
