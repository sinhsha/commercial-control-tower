"""
AutoModelSelector
=================
Selects the best forecast model based on walk-forward evaluation results.

Selection rules (applied in order):
  1. Lowest WAPE
  2. Lowest |bias| (tie-breaker)
  3. Fastest runtime_ms (second tie-breaker)

Per-hotel evaluation results are cached in-memory with a configurable TTL.
"""
from __future__ import annotations

import logging
import time
from datetime import date

from app.schemas.forecasting import EvaluationResult
from app.services.forecasting.comparison import ForecastComparisonService
from app.services.forecasting.evaluation import EvaluationWindow

logger = logging.getLogger(__name__)


class _CacheEntry:
    __slots__ = ("model_id", "reason", "expires_at")

    def __init__(self, model_id: str, reason: str, expires_at: float) -> None:
        self.model_id = model_id
        self.reason = reason
        self.expires_at = expires_at


class AutoModelSelector:
    """Caching auto-selection of the best registered forecast model."""

    def __init__(
        self,
        comparison_svc: ForecastComparisonService,
        ttl_seconds: int = 3600,
        window: EvaluationWindow = "last_30",
    ) -> None:
        self._comparison_svc = comparison_svc
        self._ttl = ttl_seconds
        self._window = window
        self._cache: dict[str, _CacheEntry] = {}

    async def select(
        self,
        hotel_id: str,
        history: list[tuple[date, float]],
    ) -> tuple[str, str]:
        """
        Return (model_id, reason).
        Uses cached result if within TTL.
        """
        entry = self._cache.get(hotel_id)
        if entry is not None and time.monotonic() < entry.expires_at:
            logger.debug(
                "AutoModelSelector cache hit: hotel=%s model=%s",
                hotel_id, entry.model_id,
            )
            return entry.model_id, entry.reason

        comparison = await self._comparison_svc.compare(
            hotel_id=hotel_id,
            history=history,
            window=self._window,
        )

        selected_id = comparison.recommended_model_id
        reason = _build_reason(comparison.models, selected_id)

        self._cache[hotel_id] = _CacheEntry(
            model_id=selected_id,
            reason=reason,
            expires_at=time.monotonic() + self._ttl,
        )
        logger.info(
            "AutoModelSelector selected model=%s for hotel=%s reason=%s",
            selected_id, hotel_id, reason,
        )
        return selected_id, reason

    def invalidate(self, hotel_id: str) -> None:
        self._cache.pop(hotel_id, None)


# ── Helper ────────────────────────────────────────────────────────────────────

def select_best(results: list[EvaluationResult]) -> tuple[str, str]:
    """
    Stateless selection helper used in tests.
    Returns (model_id, reason).
    """
    if not results:
        return "seasonal_baseline", "no evaluation results available"

    best = min(results, key=lambda r: (r.wape, abs(r.bias), r.runtime_ms))
    reason = _build_reason(results, best.model_id)
    return best.model_id, reason


def _build_reason(results: list[EvaluationResult], selected_id: str) -> str:
    selected = next((r for r in results if r.model_id == selected_id), None)
    if selected is None:
        return "selected by default"
    return (
        f"WAPE={selected.wape:.2f}%, "
        f"Bias={selected.bias:.2f}pp, "
        f"Runtime={selected.runtime_ms:.1f}ms"
    )
