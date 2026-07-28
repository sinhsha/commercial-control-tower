from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.core.dependencies import get_hotel_service
from app.schemas.hotel import (
    HotelCreate,
    HotelListResponse,
    HotelResponse,
    HotelUpdate,
)
from app.services.hotel_service import HotelService

router = APIRouter(prefix="/hotels", tags=["hotels"])
logger = logging.getLogger(__name__)


@router.get("", response_model=HotelListResponse, summary="List hotels")
async def list_hotels(
    service: Annotated[HotelService, Depends(get_hotel_service)],
    active_only: bool = Query(True, description="Filter to active hotels only"),
) -> HotelListResponse:
    hotels = await service.list_hotels(active_only=active_only)
    return HotelListResponse(
        total=len(hotels),
        items=[HotelResponse.model_validate(h) for h in hotels],
    )


@router.get("/{hotel_id}", response_model=HotelResponse, summary="Get hotel by ID")
async def get_hotel(
    hotel_id: str,
    service: Annotated[HotelService, Depends(get_hotel_service)],
) -> HotelResponse:
    hotel = await service.get_hotel(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    return HotelResponse.model_validate(hotel)


@router.post(
    "",
    response_model=HotelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create hotel",
)
async def create_hotel(
    data: HotelCreate,
    service: Annotated[HotelService, Depends(get_hotel_service)],
) -> HotelResponse:
    hotel = await service.create_hotel(data)
    return HotelResponse.model_validate(hotel)


@router.patch("/{hotel_id}", response_model=HotelResponse, summary="Update hotel")
async def update_hotel(
    hotel_id: str,
    data: HotelUpdate,
    service: Annotated[HotelService, Depends(get_hotel_service)],
) -> HotelResponse:
    hotel = await service.update_hotel(hotel_id, data)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    return HotelResponse.model_validate(hotel)
