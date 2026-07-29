"""
Commercial Recommendations endpoint.

Architecture
────────────
This endpoint is a thin HTTP controller.  All logic lives in
RecommendationService (injected via DI).  The endpoint:

    1. Validates the hotel exists.
    2. Resolves the as_of date (latest historical date if not supplied).
    3. Delegates to RecommendationService.generate_recommendations().
    4. Applies optional query-param filtering (category, priority, status).
    5. Returns a RecommendationResponse.

The recommendation engine is pluggable: changing get_recommendation_service()
in app/core/dependencies.py is the only change needed to swap the engine.

Failures in the recommendation service return HTTP 503 (not 500) so the
frontend can distinguish "engine unavailable" from a server crash, and keep
other dashboard panels working.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import (
    get_metrics_repository,
    get_hotel_repository,
    get_recommendation_service,
)
from app.repositories.hotel_repository import HotelRepository
from app.repositories.metrics_repository import MetricsRepository
from app.schemas.recommendations import (
    Recommendation,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationResponse,
    RecommendationStatus,
)
from app.services.recommendations.base import RecommendationService

router = APIRouter(prefix="/hotels", tags=["recommendations"])
logger = logging.getLogger(__name__)

_MAX_HORIZON: int = 90
_DEFAULT_HORIZON: int = 14
_DEFAULT_LIMIT: int = 10


@router.get(
    "/{hotel_id}/recommendations",
    response_model=RecommendationResponse,
    summary="Commercial recommendations",
    description=(
        "Returns ranked commercial recommendations for the property based on the "
        "current forecast, event-adjusted forecast, demand events, inventory position, "
        "and mock market signals.  Supports filtering by category, priority, and status."
    ),
)
async def list_recommendations(
    hotel_id: str,
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    metrics_repo: Annotated[MetricsRepository, Depends(get_metrics_repository)],
    rec_svc: Annotated[RecommendationService, Depends(get_recommendation_service)],
    as_of: date | None = Query(None, description="Origin date (defaults to latest available)"),
    days: int = Query(_DEFAULT_HORIZON, ge=1, le=_MAX_HORIZON, description="Forecast horizon"),
    category: RecommendationCategory | None = Query(None, description="Filter by category"),
    priority: RecommendationPriority | None = Query(None, description="Filter by priority"),
    rec_status: RecommendationStatus = Query(
        RecommendationStatus.proposed,
        alias="status",
        description="Filter by status",
    ),
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=50, description="Maximum results"),
) -> RecommendationResponse:

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

    # ── Generate recommendations ──────────────────────────────────────────────
    try:
        result = await rec_svc.generate_recommendations(
            hotel_id=hotel_id,
            as_of=origin,
            horizon_days=days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        logger.exception("Recommendation engine error for hotel %s: %s", hotel_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Recommendation engine temporarily unavailable",
        )

    # ── Apply filters ─────────────────────────────────────────────────────────
    filtered: list[Recommendation] = result.recommendations
    if category is not None:
        filtered = [r for r in filtered if r.category == category]
    if priority is not None:
        filtered = [r for r in filtered if r.priority == priority]
    filtered = [r for r in filtered if r.status == rec_status]
    filtered = filtered[:limit]

    # Rebuild summary for the filtered slice
    from app.schemas.recommendations import RecommendationSummary

    summary = RecommendationSummary(
        total=len(filtered),
        critical=sum(1 for r in filtered if r.priority.value == "critical"),
        high=sum(1 for r in filtered if r.priority.value == "high"),
        medium=sum(1 for r in filtered if r.priority.value == "medium"),
        low=sum(1 for r in filtered if r.priority.value == "low"),
        estimated_revenue_opportunity=round(sum(r.expected_revenue_impact for r in filtered), 0),
    )

    return RecommendationResponse(
        hotel_id=result.hotel_id,
        generated_at=result.generated_at,
        forecast_model=result.forecast_model,
        adjustment_model=result.adjustment_model,
        recommendation_model=result.recommendation_model,
        summary=summary,
        recommendations=filtered,
    )


@router.get(
    "/{hotel_id}/recommendations/{recommendation_id}",
    response_model=Recommendation,
    summary="Single recommendation detail",
    description=(
        "Returns a single recommendation by its stable deterministic ID. "
        "Recommendations are generated on-demand; the full set is regenerated "
        "and then filtered to the requested ID."
    ),
)
async def get_recommendation(
    hotel_id: str,
    recommendation_id: str,
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    metrics_repo: Annotated[MetricsRepository, Depends(get_metrics_repository)],
    rec_svc: Annotated[RecommendationService, Depends(get_recommendation_service)],
    as_of: date | None = Query(None),
    days: int = Query(_DEFAULT_HORIZON, ge=1, le=_MAX_HORIZON),
) -> Recommendation:

    hotel = await hotel_repo.get_by_id(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    if as_of is None:
        latest = await metrics_repo.get_latest(hotel_id)
        if latest is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No historical data available",
            )
        origin = latest.date
    else:
        origin = as_of

    try:
        result = await rec_svc.generate_recommendations(
            hotel_id=hotel_id, as_of=origin, horizon_days=days
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        logger.exception("Recommendation engine error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Recommendation engine temporarily unavailable",
        )

    for rec in result.recommendations:
        if rec.id == recommendation_id:
            return rec

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
