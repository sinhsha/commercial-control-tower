from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_event_repository, get_hotel_repository
from app.repositories.event_repository import EventRepository
from app.repositories.hotel_repository import HotelRepository
from app.schemas.events import DemandEventResponse, EventListResponse

router = APIRouter(prefix="/hotels", tags=["events"])
logger = logging.getLogger(__name__)


@router.get(
    "/{hotel_id}/events",
    response_model=EventListResponse,
    summary="List demand events for a hotel",
    description=(
        "Returns all active and upcoming demand events associated with a hotel. "
        "Cancelled events are excluded."
    ),
)
async def list_events(
    hotel_id: str,
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    event_repo: Annotated[EventRepository, Depends(get_event_repository)],
) -> EventListResponse:
    hotel = await hotel_repo.get_by_id(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    events = await event_repo.get_active_for_hotel(hotel_id)
    return EventListResponse(
        total=len(events),
        items=[DemandEventResponse.model_validate(e) for e in events],
    )
