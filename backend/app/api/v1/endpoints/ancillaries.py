"""
Ancillary Revenue endpoints.

Architecture
────────────
Thin HTTP controllers – all logic lives in AncillaryRecommendationService
and AncillaryCatalogService (injected via DI).  The endpoints:

1. GET /hotels/{hotel_id}/ancillaries
       Returns full active product catalog.

2. GET /hotels/{hotel_id}/ancillary-recommendations
       Generates ranked ancillary offers for a given persona / horizon.
       Query params: persona, as_of, days, limit, category

3. GET /hotels/{hotel_id}/ancillary-recommendations/{ancillary_code}
       Returns a single ancillary recommendation by product code.

Engine failures return HTTP 503 (non-fatal) so other dashboard panels
continue to function.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import (
    get_ancillary_catalog_service,
    get_ancillary_recommendation_service,
    get_hotel_repository,
    get_metrics_repository,
)
from app.repositories.hotel_repository import HotelRepository
from app.repositories.metrics_repository import MetricsRepository
from app.schemas.ancillaries import (
    AncillaryCatalogResponse,
    AncillaryCategory,
    AncillaryRecommendation,
    AncillaryRecommendationResponse,
    GuestPersona,
)
from app.services.ancillaries.base import AncillaryRecommendationService
from app.services.ancillaries.catalog import AncillaryCatalogService

router = APIRouter(prefix="/hotels", tags=["ancillaries"])
logger = logging.getLogger(__name__)

_MAX_HORIZON: int = 90
_DEFAULT_HORIZON: int = 14
_DEFAULT_LIMIT: int = 5


# ── GET catalog ───────────────────────────────────────────────────────────────


@router.get(
    "/{hotel_id}/ancillaries",
    response_model=AncillaryCatalogResponse,
    summary="Ancillary product catalog",
    description=(
        "Returns the full active ancillary product catalog for the property. "
        "Products are seeded and do not vary by hotel in this iteration."
    ),
)
async def list_ancillaries(
    hotel_id: str,
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    catalog_svc: Annotated[AncillaryCatalogService, Depends(get_ancillary_catalog_service)],
) -> AncillaryCatalogResponse:

    hotel = await hotel_repo.get_by_id(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    products = catalog_svc.get_active_products()
    return AncillaryCatalogResponse(
        hotel_id=hotel_id,
        total=len(products),
        items=products,
    )


# ── GET recommendations ───────────────────────────────────────────────────────


@router.get(
    "/{hotel_id}/ancillary-recommendations",
    response_model=AncillaryRecommendationResponse,
    summary="Ancillary revenue recommendations",
    description=(
        "Returns ranked ancillary revenue offers for the property. "
        "Filters by persona, category, and horizon.  "
        "The engine context (occupancy, demand, events) is built from live hotel data."
    ),
)
async def list_ancillary_recommendations(
    hotel_id: str,
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    metrics_repo: Annotated[MetricsRepository, Depends(get_metrics_repository)],
    svc: Annotated[AncillaryRecommendationService, Depends(get_ancillary_recommendation_service)],
    persona: GuestPersona = Query(
        GuestPersona.hotel_wide, description="Guest persona filter"
    ),
    as_of: date | None = Query(None, description="Origin date (defaults to latest)"),
    days: int = Query(_DEFAULT_HORIZON, ge=1, le=_MAX_HORIZON, description="Forecast horizon"),
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=20, description="Maximum results"),
    category: AncillaryCategory | None = Query(None, description="Filter by category"),
) -> AncillaryRecommendationResponse:

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

    # ── Generate ──────────────────────────────────────────────────────────────
    try:
        result = await svc.generate_recommendations(
            hotel_id=hotel_id,
            as_of=origin,
            persona=persona,
            horizon_days=days,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        logger.exception("Ancillary engine error for hotel %s: %s", hotel_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ancillary recommendation engine temporarily unavailable",
        )

    # ── Category filter ───────────────────────────────────────────────────────
    if category is not None:
        filtered = [
            r for r in result.recommendations if r.product.category == category
        ]
        result = result.model_copy(
            update={
                "recommendations": filtered,
                "summary": result.summary.model_copy(
                    update={
                        "shown": len(filtered),
                        "total_revenue_opportunity": round(
                            sum(r.expected_revenue for r in filtered), 2
                        ),
                        "total_margin_opportunity": round(
                            sum(r.expected_margin for r in filtered), 2
                        ),
                    }
                ),
            }
        )

    return result


# ── GET single recommendation ─────────────────────────────────────────────────


@router.get(
    "/{hotel_id}/ancillary-recommendations/{ancillary_code}",
    response_model=AncillaryRecommendation,
    summary="Single ancillary recommendation detail",
    description=(
        "Returns a single ancillary recommendation by product code. "
        "The full set is regenerated and filtered to the requested code."
    ),
)
async def get_ancillary_recommendation(
    hotel_id: str,
    ancillary_code: str,
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    metrics_repo: Annotated[MetricsRepository, Depends(get_metrics_repository)],
    svc: Annotated[AncillaryRecommendationService, Depends(get_ancillary_recommendation_service)],
    persona: GuestPersona = Query(GuestPersona.hotel_wide),
    as_of: date | None = Query(None),
    days: int = Query(_DEFAULT_HORIZON, ge=1, le=_MAX_HORIZON),
) -> AncillaryRecommendation:

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
        result = await svc.generate_recommendations(
            hotel_id=hotel_id,
            as_of=origin,
            persona=persona,
            horizon_days=days,
            limit=20,  # get all to find the one by code
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        logger.exception("Ancillary engine error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ancillary recommendation engine temporarily unavailable",
        )

    for rec in result.recommendations:
        if rec.product.code.upper() == ancillary_code.upper():
            return rec

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Ancillary recommendation for code {ancillary_code!r} not found or suppressed",
    )
