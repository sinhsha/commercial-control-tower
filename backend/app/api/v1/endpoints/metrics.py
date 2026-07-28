from __future__ import annotations

import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import get_metrics_service
from app.schemas.hotel import DailyMetricsListResponse, DailyMetricsResponse, DashboardSummary
from app.services.metrics_service import MetricsService

router = APIRouter(prefix="/metrics", tags=["metrics"])
logger = logging.getLogger(__name__)


@router.get(
    "/dashboard/{hotel_id}",
    response_model=DashboardSummary,
    summary="Commercial dashboard for a hotel",
)
async def get_dashboard(
    hotel_id: str,
    service: Annotated[MetricsService, Depends(get_metrics_service)],
    as_of: date | None = Query(None, description="Date to snapshot (defaults to today)"),
) -> DashboardSummary:
    """
    Returns the full commercial KPI dashboard for a hotel:
    occupancy %, ADR, RevPAR, available rooms, and 30-day demand trend.
    """
    summary = await service.get_dashboard(hotel_id, as_of=as_of)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hotel not found or no metrics available",
        )
    return summary


@router.get(
    "/range/{hotel_id}",
    response_model=DailyMetricsListResponse,
    summary="Historical metrics for a date range",
)
async def get_metrics_range(
    hotel_id: str,
    service: Annotated[MetricsService, Depends(get_metrics_service)],
    start: date = Query(..., description="Start date (inclusive)"),
    end: date = Query(..., description="End date (inclusive)"),
) -> DailyMetricsListResponse:
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start must be ≤ end",
        )
    records = await service.get_metrics_range(hotel_id, start, end)
    return DailyMetricsListResponse(
        total=len(records),
        items=[DailyMetricsResponse.model_validate(r) for r in records],
    )
