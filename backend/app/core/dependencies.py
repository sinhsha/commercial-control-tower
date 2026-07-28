"""
Dependency-injection container.

Each service is exposed as a FastAPI dependency factory so callsites
never instantiate services directly.  Swap an implementation by
changing the factory – no callsite modifications required.

To replace the forecasting engine (e.g. with TimesFMForecastService):
  Change only `get_forecast_service` to return the new implementation.
  The endpoint, schema, and frontend are unaffected.

To replace the event-adjustment engine (e.g. with MLEventEngineService):
  Change only `get_event_engine_service` to return the new implementation.
"""
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.repositories.hotel_repository import HotelRepository
from app.repositories.metrics_repository import MetricsRepository
from app.repositories.event_repository import EventRepository
from app.services.hotel_service import HotelService
from app.services.metrics_service import MetricsService
from app.services.forecasting.base import ForecastService
from app.services.forecasting.seasonal_baseline import SeasonalBaselineForecastService
from app.services.events.base import EventImpactService
from app.services.events.default_impact import DefaultEventImpactService
from app.services.event_engine.base import EventEngineService
from app.services.event_engine.rule_based import RuleBasedEventEngineService


# ── Repositories ─────────────────────────────────────────────────────────────

def get_hotel_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HotelRepository:
    return HotelRepository(session)


def get_metrics_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MetricsRepository:
    return MetricsRepository(session)


# ── Services ──────────────────────────────────────────────────────────────────

def get_hotel_service(
    repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
) -> HotelService:
    return HotelService(repo)


def get_metrics_service(
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    metrics_repo: Annotated[MetricsRepository, Depends(get_metrics_repository)],
) -> MetricsService:
    return MetricsService(hotel_repo, metrics_repo)


def get_forecast_service() -> ForecastService:
    """
    Factory for the active forecasting implementation.

    Swap this return value to change the engine project-wide:
        return TimesFMForecastService()
    """
    return SeasonalBaselineForecastService()


def get_event_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EventRepository:
    return EventRepository(session)


def get_event_impact_service() -> EventImpactService:
    """
    Factory for the active event-impact engine.

    Swap this return value to change the event-impact model project-wide:
        return MLEventImpactService()
    """
    return DefaultEventImpactService()


def get_event_engine_service(
    impact_svc: Annotated[EventImpactService, Depends(get_event_impact_service)],
) -> EventEngineService:
    """
    Factory for the active event-adjustment engine.

    The engine is a composition layer on top of EventImpactService.
    Swap this return value to change the adjustment engine project-wide:
        return MLEventEngineService(impact_svc)
    """
    return RuleBasedEventEngineService(impact_svc)
