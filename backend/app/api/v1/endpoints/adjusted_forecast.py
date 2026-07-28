"""
Adjusted-forecast endpoint.

Architecture
────────────
This endpoint COMPOSES three independent services without modifying any:

    1. ForecastService      → produces baseline ForecastPoint[]
    2. EventEngineService   → applies event signals and confidence weighting
                              to produce AdjustedForecastDay[]
    3. This module          → orchestrates the two + handles HTTP concerns

Neither ForecastService nor EventEngineService know about each other.
The endpoint wires them together and marshals the result into the API schema.

Response matches the agreed spec:
    {
        "model": "Seasonal Baseline",
        "adjustment_model": "Rule Based Event Engine",
        "days": [{
            "date": "...",
            "baseline": 74.3,
            "adjusted": 82.8,
            "uplift": 8.5,
            "confidence_low": ...,
            "confidence_high": ...,
            "reasons": ["Comic Con", "Weekend demand"]
        }]
    }
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import (
    get_event_engine_service,
    get_event_repository,
    get_forecast_service,
    get_hotel_repository,
    get_metrics_repository,
)
from app.repositories.event_repository import EventRepository
from app.repositories.hotel_repository import HotelRepository
from app.repositories.metrics_repository import MetricsRepository
from app.schemas.events import AdjustedForecastResponse
from app.services.event_engine.base import EventEngineService
from app.services.forecasting.base import ForecastService

router = APIRouter(prefix="/hotels", tags=["adjusted-forecast"])
logger = logging.getLogger(__name__)

_MAX_HORIZON: int = 90
_HISTORY_WINDOW: int = 90


@router.get(
    "/{hotel_id}/forecast/adjusted",
    response_model=AdjustedForecastResponse,
    summary="Event-adjusted occupancy forecast",
    description=(
        "Returns a forecast where the baseline signal is augmented with "
        "contributions from nearby demand events weighted by confidence. "
        "Both baseline and adjusted series are returned so the frontend "
        "can toggle between them. Each adjusted date includes the reasons "
        "(event names) that drove the adjustment."
    ),
)
async def get_adjusted_forecast(
    hotel_id: str,
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    metrics_repo: Annotated[MetricsRepository, Depends(get_metrics_repository)],
    event_repo: Annotated[EventRepository, Depends(get_event_repository)],
    forecast_svc: Annotated[ForecastService, Depends(get_forecast_service)],
    engine_svc: Annotated[EventEngineService, Depends(get_event_engine_service)],
    days: int = Query(14, ge=1, le=_MAX_HORIZON, description="Forecast horizon in days"),
    as_of: date | None = Query(None, description="Origin date (defaults to latest available)"),
) -> AdjustedForecastResponse:

    # ── Validate hotel ────────────────────────────────────────────────────────
    hotel = await hotel_repo.get_by_id(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    # ── Resolve origin ────────────────────────────────────────────────────────
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

    # ── Baseline forecast (unchanged) ─────────────────────────────────────────
    history_start = origin - timedelta(days=_HISTORY_WINDOW - 1)
    records = await metrics_repo.get_range(hotel_id, history_start, origin)

    if len(records) < forecast_svc.min_history_days:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Insufficient history: model '{forecast_svc.model_name}' needs "
                f"≥ {forecast_svc.min_history_days} days, only {len(records)} available."
            ),
        )

    history = [(r.date, r.occupancy_pct) for r in records]
    baseline_points = await forecast_svc.forecast(
        hotel_id=hotel_id,
        history=history,
        horizon=days,
        origin=origin,
    )

    # ── Fetch events that overlap the forecast window ─────────────────────────
    forecast_end = origin + timedelta(days=days)
    events = await event_repo.get_overlapping(hotel_id, origin + timedelta(days=1), forecast_end)

    # ── Apply event engine (confidence-weighted uplifts) ──────────────────────
    adjusted_days = engine_svc.apply(
        hotel_id=hotel_id,
        hotel_total_rooms=hotel.total_rooms,
        forecast_origin_date=origin,
        baseline=baseline_points,
        events=events,
    )

    return AdjustedForecastResponse(
        hotel_id=hotel_id,
        model=forecast_svc.model_name,
        adjustment_model=engine_svc.engine_name,
        origin_date=origin,
        horizon=days,
        days=adjusted_days,
    )
