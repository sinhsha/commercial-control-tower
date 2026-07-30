from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.dependencies import get_event_repository, get_hotel_repository
from app.models.demand_event import DemandEvent
from app.repositories.event_repository import EventRepository
from app.repositories.hotel_repository import HotelRepository
from app.schemas.events import (
    CreateDemandEventRequest,
    DemandEventResponse,
    EventListResponse,
)

router = APIRouter(prefix="/hotels", tags=["events"])
logger = logging.getLogger(__name__)


@router.get(
    "/{hotel_id}/events",
    response_model=EventListResponse,
    summary="List demand events for a hotel",
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


@router.post(
    "/{hotel_id}/events",
    response_model=DemandEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a demand event for a hotel",
)
async def create_event(
    hotel_id: str,
    body: CreateDemandEventRequest,
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    event_repo: Annotated[EventRepository, Depends(get_event_repository)],
) -> DemandEventResponse:
    hotel = await hotel_repo.get_by_id(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    event = DemandEvent(
        hotel_id=hotel_id,
        name=body.name,
        event_type=body.event_type,
        start_date=body.start_date,
        end_date=body.end_date,
        distance_miles=body.distance_miles,
        expected_attendance=body.expected_attendance,
        impact_strength=body.impact_strength,
        confidence=body.confidence,
        status=body.status,
    )
    saved = await event_repo.create(event)
    logger.info("Created event %s for hotel %s", saved.id, hotel_id)
    return DemandEventResponse.model_validate(saved)


@router.delete(
    "/{hotel_id}/events/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a demand event",
)
async def delete_event(
    hotel_id: str,
    event_id: str,
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    event_repo: Annotated[EventRepository, Depends(get_event_repository)],
) -> Response:
    hotel = await hotel_repo.get_by_id(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    event = await event_repo.get_by_id(event_id)
    if event is None or event.hotel_id != hotel_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    await event_repo.delete(event)
    logger.info("Deleted event %s from hotel %s", event_id, hotel_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
