"""
Dynamic Room Pricing & Inventory Optimization endpoints.

Architecture
────────────
Thin HTTP controllers; all logic lives in RoomPricingService (injected via DI).
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import (
    get_hotel_repository,
    get_metrics_repository,
    get_room_pricing_service,
)
from app.repositories.hotel_repository import HotelRepository
from app.repositories.metrics_repository import MetricsRepository
from app.schemas.room_pricing import (
    InventoryResponse,
    RoomCalendarResponse,
    RoomPricingResponse,
    RoomTypePricingRecommendation,
)
from app.services.room_pricing.base import RoomPricingService

router = APIRouter(prefix="/hotels", tags=["room-pricing"])
logger = logging.getLogger(__name__)

_DEFAULT_HORIZON: int = 14
_MAX_HORIZON: int = 90


async def _resolve_origin(
    hotel_id: str,
    as_of: date | None,
    metrics_repo: MetricsRepository,
) -> date:
    if as_of is not None:
        return as_of
    latest = await metrics_repo.get_latest(hotel_id)
    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No historical data available for this hotel",
        )
    return latest.date


@router.get(
    "/{hotel_id}/room-pricing",
    response_model=RoomPricingResponse,
    summary="Dynamic room pricing recommendations",
)
async def get_room_pricing(
    hotel_id: str,
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    metrics_repo: Annotated[MetricsRepository, Depends(get_metrics_repository)],
    pricing_svc: Annotated[RoomPricingService, Depends(get_room_pricing_service)],
    as_of: date | None = Query(None),
    days: int = Query(_DEFAULT_HORIZON, ge=1, le=_MAX_HORIZON),
) -> RoomPricingResponse:
    hotel = await hotel_repo.get_by_id(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    origin = await _resolve_origin(hotel_id, as_of, metrics_repo)
    try:
        return await pricing_svc.generate_recommendations(
            hotel_id=hotel_id, as_of=origin, horizon_days=days
        )
    except Exception as exc:
        logger.exception("Room pricing error for hotel %s: %s", hotel_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Room pricing engine temporarily unavailable",
        )


@router.get(
    "/{hotel_id}/room-calendar",
    response_model=RoomCalendarResponse,
    summary="Per-room-type pricing calendar",
)
async def get_room_calendar(
    hotel_id: str,
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    metrics_repo: Annotated[MetricsRepository, Depends(get_metrics_repository)],
    pricing_svc: Annotated[RoomPricingService, Depends(get_room_pricing_service)],
    as_of: date | None = Query(None),
    days: int = Query(_DEFAULT_HORIZON, ge=1, le=_MAX_HORIZON),
) -> RoomCalendarResponse:
    hotel = await hotel_repo.get_by_id(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    origin = await _resolve_origin(hotel_id, as_of, metrics_repo)
    try:
        return await pricing_svc.get_calendar(
            hotel_id=hotel_id, as_of=origin, horizon_days=days
        )
    except Exception as exc:
        logger.exception("Room calendar error for hotel %s: %s", hotel_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Room calendar engine temporarily unavailable",
        )


@router.get(
    "/{hotel_id}/inventory",
    response_model=InventoryResponse,
    summary="Room inventory status",
)
async def get_inventory(
    hotel_id: str,
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    metrics_repo: Annotated[MetricsRepository, Depends(get_metrics_repository)],
    pricing_svc: Annotated[RoomPricingService, Depends(get_room_pricing_service)],
    as_of: date | None = Query(None),
) -> InventoryResponse:
    hotel = await hotel_repo.get_by_id(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    origin = await _resolve_origin(hotel_id, as_of, metrics_repo)
    try:
        return await pricing_svc.get_inventory(hotel_id=hotel_id, as_of=origin)
    except Exception as exc:
        logger.exception("Inventory error for hotel %s: %s", hotel_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Inventory engine temporarily unavailable",
        )


@router.get(
    "/{hotel_id}/pricing-explanation/{room_code}",
    response_model=RoomTypePricingRecommendation,
    summary="Single room-type pricing explanation",
)
async def get_pricing_explanation(
    hotel_id: str,
    room_code: str,
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    metrics_repo: Annotated[MetricsRepository, Depends(get_metrics_repository)],
    pricing_svc: Annotated[RoomPricingService, Depends(get_room_pricing_service)],
    as_of: date | None = Query(None),
    days: int = Query(_DEFAULT_HORIZON, ge=1, le=_MAX_HORIZON),
) -> RoomTypePricingRecommendation:
    hotel = await hotel_repo.get_by_id(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    origin = await _resolve_origin(hotel_id, as_of, metrics_repo)
    try:
        result = await pricing_svc.generate_recommendations(
            hotel_id=hotel_id, as_of=origin, horizon_days=days
        )
    except Exception as exc:
        logger.exception("Pricing explanation error for hotel %s: %s", hotel_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Room pricing engine temporarily unavailable",
        )

    for rec in result.recommendations:
        if rec.code.upper() == room_code.upper():
            return rec

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Room type '{room_code}' not found for this hotel",
    )
