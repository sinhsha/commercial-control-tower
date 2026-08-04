from fastapi import APIRouter

from app.api.v1.endpoints import (
    health,
    hotels,
    metrics,
    forecast,
    events,
    adjusted_forecast,
    recommendations,
    ancillaries,
    copilot,
    forecast_platform,
    room_pricing,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(hotels.router)
api_router.include_router(metrics.router)
api_router.include_router(forecast.router)
api_router.include_router(events.router)
api_router.include_router(adjusted_forecast.router)
api_router.include_router(recommendations.router)
api_router.include_router(ancillaries.router)
api_router.include_router(copilot.router)
api_router.include_router(forecast_platform.router)
api_router.include_router(room_pricing.router)
