"""
Enterprise Forecasting Platform — API endpoints.

GET /api/v1/forecast/models        — list registered models
GET /api/v1/forecast/evaluation    — run/return evaluation metrics
GET /api/v1/forecast/comparison    — side-by-side model comparison
GET /api/v1/forecast/health        — traffic-light health status
GET /api/v1/forecast/backtest      — backtest with actuals/predicted/residuals
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import (
    get_forecast_comparison_service,
    get_forecast_evaluation_service,
    get_forecast_manager_service,
    get_forecast_model_registry,
    get_metrics_repository,
    get_hotel_repository,
)
from app.repositories.hotel_repository import HotelRepository
from app.repositories.metrics_repository import MetricsRepository
from app.schemas.forecasting import (
    BacktestResult,
    ComparisonResult,
    EvaluationResult,
    ForecastHealthStatus,
    ForecastModelInfo,
    ForecastModelListResponse,
    ManagedForecastResult,
)
from app.services.forecasting.comparison import ForecastComparisonService
from app.services.forecasting.evaluation import ForecastEvaluationService, EvaluationWindow
from app.services.forecasting.manager import ForecastManagerService
from app.services.forecasting.model_registry import ForecastModelRegistry

router = APIRouter(prefix="/forecast", tags=["forecast-platform"])
logger = logging.getLogger(__name__)

_HISTORY_WINDOW = 120  # days to fetch from DB for evaluation / comparison


# ── GET /forecast/models ──────────────────────────────────────────────────────

@router.get(
    "/models",
    response_model=ForecastModelListResponse,
    summary="List registered forecast models",
)
async def list_models(
    registry: Annotated[ForecastModelRegistry, Depends(get_forecast_model_registry)],
) -> ForecastModelListResponse:
    models = [
        ForecastModelInfo(
            model_id=m.model_id,
            name=m.name,
            version=m.version,
            provider=m.provider,
            device=m.device,
            supported_horizons=m.supported_horizons,
            capabilities=m.capabilities,
            status=m.status,
        )
        for m in registry.list_all()
    ]
    return ForecastModelListResponse(total=len(models), models=models)


# ── GET /forecast/evaluation ──────────────────────────────────────────────────

@router.get(
    "/evaluation",
    response_model=EvaluationResult,
    summary="Run walk-forward evaluation for a model",
)
async def get_evaluation(
    hotel_id: str = Query(..., description="Hotel ID"),
    window: Literal["last_30", "last_60", "last_90"] = Query(
        "last_30", description="Evaluation window"
    ),
    model: Literal["baseline", "timesfm"] = Query(
        "baseline", description="Model to evaluate"
    ),
    hotel_repo: HotelRepository = Depends(get_hotel_repository),
    metrics_repo: MetricsRepository = Depends(get_metrics_repository),
    eval_svc: ForecastEvaluationService = Depends(get_forecast_evaluation_service),
) -> EvaluationResult:
    hotel = await hotel_repo.get_by_id(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    history = await _fetch_history(hotel_id, metrics_repo)
    model_id = "seasonal_baseline" if model == "baseline" else "timesfm"

    return await eval_svc.evaluate(
        hotel_id=hotel_id,
        history=history,
        window=_to_eval_window(window),
        model_id=model_id,
    )


# ── GET /forecast/comparison ──────────────────────────────────────────────────

@router.get(
    "/comparison",
    response_model=ComparisonResult,
    summary="Side-by-side model comparison",
)
async def get_comparison(
    hotel_id: str = Query(..., description="Hotel ID"),
    days: int = Query(30, ge=7, le=90, description="Evaluation window in days"),
    hotel_repo: HotelRepository = Depends(get_hotel_repository),
    metrics_repo: MetricsRepository = Depends(get_metrics_repository),
    comparison_svc: ForecastComparisonService = Depends(get_forecast_comparison_service),
) -> ComparisonResult:
    hotel = await hotel_repo.get_by_id(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    history = await _fetch_history(hotel_id, metrics_repo)
    window = _days_to_window(days)

    return await comparison_svc.compare(
        hotel_id=hotel_id,
        history=history,
        window=window,
    )


# ── GET /forecast/health ──────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=ForecastHealthStatus,
    summary="Traffic-light forecast health status",
)
async def get_health(
    hotel_id: str = Query(..., description="Hotel ID"),
    hotel_repo: HotelRepository = Depends(get_hotel_repository),
    metrics_repo: MetricsRepository = Depends(get_metrics_repository),
    manager_svc: ForecastManagerService = Depends(get_forecast_manager_service),
    registry: ForecastModelRegistry = Depends(get_forecast_model_registry),
) -> ForecastHealthStatus:
    hotel = await hotel_repo.get_by_id(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    history = await _fetch_history(hotel_id, metrics_repo)

    if not history:
        return ForecastHealthStatus(
            hotel_id=hotel_id,
            status="degraded",
            active_model="seasonal_baseline",
            active_model_version="1.0.0",
            fallback_active=False,
            last_validation=datetime.now(timezone.utc),
            warnings=["No historical data available"],
        )

    origin = history[-1][0]

    # Run a quick 7-day managed forecast to check governance
    result = await manager_svc.forecast(
        hotel_id=hotel_id,
        history=history,
        horizon=7,
        origin=origin,
    )

    # Determine traffic light
    if result.validation_status == "passed" and not result.fallback_used:
        health_status = "healthy"
    elif result.validation_status == "warning" or result.fallback_used:
        health_status = "warning"
    else:
        health_status = "degraded"

    active_model_entry = registry.get(result.model_used)
    model_version = active_model_entry.version if active_model_entry else "1.0.0"

    return ForecastHealthStatus(
        hotel_id=hotel_id,
        status=health_status,
        active_model=result.model_used,
        active_model_version=model_version,
        fallback_active=result.fallback_used,
        last_validation=result.generated_at,
        warnings=result.warnings,
    )


# ── GET /forecast/backtest ────────────────────────────────────────────────────

@router.get(
    "/backtest",
    response_model=BacktestResult,
    summary="Backtest with actuals vs predicted + residuals",
)
async def get_backtest(
    hotel_id: str = Query(..., description="Hotel ID"),
    window: Literal["last_30", "last_60", "last_90"] = Query(
        "last_30", description="Backtest window"
    ),
    model: Literal["baseline", "timesfm"] = Query(
        "baseline", description="Model to backtest"
    ),
    hotel_repo: HotelRepository = Depends(get_hotel_repository),
    metrics_repo: MetricsRepository = Depends(get_metrics_repository),
    eval_svc: ForecastEvaluationService = Depends(get_forecast_evaluation_service),
) -> BacktestResult:
    hotel = await hotel_repo.get_by_id(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    history = await _fetch_history(hotel_id, metrics_repo)
    model_id = "seasonal_baseline" if model == "baseline" else "timesfm"

    return await eval_svc.backtest(
        hotel_id=hotel_id,
        history=history,
        window=_to_eval_window(window),
        model_id=model_id,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _fetch_history(
    hotel_id: str,
    metrics_repo: MetricsRepository,
) -> list[tuple[date, float]]:
    """Fetch the last _HISTORY_WINDOW days of occupancy as (date, pct) pairs."""
    latest = await metrics_repo.get_latest(hotel_id)
    if latest is None:
        return []
    end = latest.date
    start = end - timedelta(days=_HISTORY_WINDOW - 1)
    records = await metrics_repo.get_range(hotel_id, start, end)
    return [(r.date, r.occupancy_pct) for r in records]


def _to_eval_window(s: str) -> EvaluationWindow:
    mapping: dict[str, EvaluationWindow] = {
        "last_30": "last_30",
        "last_60": "last_60",
        "last_90": "last_90",
    }
    return mapping.get(s, "last_30")


def _days_to_window(days: int) -> EvaluationWindow:
    if days >= 60:
        return "last_60" if days < 90 else "last_90"
    return "last_30"
