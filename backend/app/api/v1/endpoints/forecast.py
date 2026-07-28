from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import (
    get_forecast_service,
    get_hotel_repository,
    get_metrics_repository,
)
from app.repositories.hotel_repository import HotelRepository
from app.repositories.metrics_repository import MetricsRepository
from app.schemas.forecast import ForecastResponse
from app.services.forecasting.base import ForecastService

router = APIRouter(prefix="/hotels", tags=["forecast"])
logger = logging.getLogger(__name__)

_MAX_HORIZON: int = 90
_HISTORY_WINDOW: int = 90  # days of history fetched for the model


@router.get(
    "/{hotel_id}/forecast",
    response_model=ForecastResponse,
    summary="14-day occupancy forecast",
    description=(
        "Returns a per-day occupancy forecast with confidence bounds. "
        "The active model is identified by `model_name` in the response. "
        "Replace the forecasting engine via dependency injection without "
        "modifying this endpoint."
    ),
)
async def get_forecast(
    hotel_id: str,
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    metrics_repo: Annotated[MetricsRepository, Depends(get_metrics_repository)],
    forecast_svc: Annotated[ForecastService, Depends(get_forecast_service)],
    days: int = Query(14, ge=1, le=_MAX_HORIZON, description="Forecast horizon in days"),
    as_of: date | None = Query(
        None,
        description="Origin date for the forecast (defaults to latest available date)",
    ),
) -> ForecastResponse:
    # ── Validate hotel exists ─────────────────────────────────────────────────
    hotel = await hotel_repo.get_by_id(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    # ── Resolve origin date ───────────────────────────────────────────────────
    if as_of is not None:
        origin = as_of
    else:
        latest = await metrics_repo.get_latest(hotel_id)
        if latest is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No historical data available for this hotel",
            )
        origin = latest.date

    # ── Fetch history window ──────────────────────────────────────────────────
    history_start = origin - timedelta(days=_HISTORY_WINDOW - 1)
    records = await metrics_repo.get_range(hotel_id, history_start, origin)

    if len(records) < forecast_svc.min_history_days:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Insufficient history: model '{forecast_svc.model_name}' needs "
                f"≥ {forecast_svc.min_history_days} days, "
                f"only {len(records)} available."
            ),
        )

    history = [(r.date, r.occupancy_pct) for r in records]

    # ── Run forecast ──────────────────────────────────────────────────────────
    points = await forecast_svc.forecast(
        hotel_id=hotel_id,
        history=history,
        horizon=days,
        origin=origin,
    )

    return ForecastResponse(
        hotel_id=hotel_id,
        model_name=forecast_svc.model_name,
        origin_date=origin,
        horizon=days,
        forecast=points,
    )
