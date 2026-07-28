from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ForecastPoint(BaseModel):
    """A single day's occupancy forecast with confidence bounds."""

    forecast_date: date
    occupancy_pct: float = Field(..., ge=0.0, le=100.0, description="Point forecast (0–100)")
    lower_bound: float = Field(..., ge=0.0, le=100.0, description="Lower confidence estimate")
    upper_bound: float = Field(..., ge=0.0, le=100.0, description="Upper confidence estimate")


class ForecastResponse(BaseModel):
    """Full response envelope returned by GET /hotels/{id}/forecast."""

    model_config = {"protected_namespaces": ()}

    hotel_id: str
    model_name: str = Field(..., description="Name of the active forecasting model")
    origin_date: date = Field(..., description="Last historical date; forecasts begin the next day")
    horizon: int = Field(..., description="Number of days forecast")
    forecast: list[ForecastPoint]
