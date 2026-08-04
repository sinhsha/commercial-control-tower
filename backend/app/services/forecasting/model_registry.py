"""
ForecastModelRegistry
=====================
Stores metadata for all registered forecast models.  Two models are
pre-registered at import time:

  • seasonal_baseline  — always available, stdlib-only implementation
  • timesfm            — graceful adapter; marked degraded if library missing
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)

ModelStatus = Literal["active", "inactive", "degraded"]


@dataclass
class ModelEntry:
    model_id: str
    name: str
    version: str
    provider: str
    device: str
    supported_horizons: list[int]
    capabilities: list[str]
    status: ModelStatus


class ForecastModelRegistry:
    """In-memory registry of forecast model metadata."""

    def __init__(self) -> None:
        self._models: dict[str, ModelEntry] = {}

    # ── Mutation ──────────────────────────────────────────────────────────────

    def register(self, entry: ModelEntry) -> None:
        self._models[entry.model_id] = entry
        logger.debug("Registered forecast model: %s (%s)", entry.model_id, entry.status)

    def set_status(self, model_id: str, status: ModelStatus) -> None:
        if model_id in self._models:
            self._models[model_id].status = status

    # ── Queries ───────────────────────────────────────────────────────────────

    def get(self, model_id: str) -> ModelEntry | None:
        return self._models.get(model_id)

    def list_all(self) -> list[ModelEntry]:
        return list(self._models.values())

    def list_active(self) -> list[ModelEntry]:
        return [m for m in self._models.values() if m.status == "active"]


# ── Module-level singleton populated at import time ───────────────────────────

def _build_default_registry() -> ForecastModelRegistry:
    registry = ForecastModelRegistry()

    registry.register(ModelEntry(
        model_id="seasonal_baseline",
        name="Seasonal Baseline",
        version="1.0.0",
        provider="internal",
        device="cpu",
        supported_horizons=list(range(1, 91)),
        capabilities=["occupancy_forecast", "confidence_intervals"],
        status="active",
    ))

    # Determine TimesFM availability
    try:
        import importlib
        importlib.util.find_spec("timesfm")
        timesfm_status: ModelStatus = "active"
    except Exception:
        timesfm_status = "degraded"

    registry.register(ModelEntry(
        model_id="timesfm",
        name="TimesFM",
        version="1.0.0",
        provider="google",
        device="cpu",
        supported_horizons=list(range(1, 97)),
        capabilities=["occupancy_forecast", "confidence_intervals", "zero_shot"],
        status=timesfm_status,
    ))

    return registry


_default_registry: ForecastModelRegistry | None = None


def get_default_registry() -> ForecastModelRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = _build_default_registry()
    return _default_registry
