from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field


class HotelBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    brand: str = Field(..., min_length=1, max_length=100)
    city: str = Field(..., min_length=1, max_length=100)
    country: str = Field(..., min_length=1, max_length=100)
    star_rating: int = Field(default=4, ge=1, le=5)
    total_rooms: int = Field(..., gt=0)
    is_active: bool = True


class HotelCreate(HotelBase):
    pass


class HotelUpdate(BaseModel):
    name: str | None = None
    brand: str | None = None
    city: str | None = None
    country: str | None = None
    star_rating: int | None = Field(default=None, ge=1, le=5)
    total_rooms: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


class HotelResponse(HotelBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class HotelListResponse(BaseModel):
    total: int
    items: list[HotelResponse]


# ── Daily Metrics ─────────────────────────────────────────────────────────────

class DailyMetricsBase(BaseModel):
    date: date
    occupied_rooms: int = Field(..., ge=0)
    total_rooms: int = Field(..., gt=0)
    adr: float = Field(..., ge=0.0)
    revenue: float = Field(..., ge=0.0)
    demand_index: float = Field(default=50.0, ge=0.0, le=100.0)
    compset_adr: float | None = None


class DailyMetricsCreate(DailyMetricsBase):
    hotel_id: str


class DailyMetricsResponse(DailyMetricsBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    hotel_id: str
    occupancy_pct: float
    revpar: float
    available_rooms: int
    created_at: datetime


class DailyMetricsListResponse(BaseModel):
    total: int
    items: list[DailyMetricsResponse]


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DemandPoint(BaseModel):
    date: date
    demand_index: float
    occupancy_pct: float
    adr: float


class DashboardSummary(BaseModel):
    hotel_id: str
    hotel_name: str
    as_of_date: date
    occupancy_pct: float = Field(..., description="Occupancy % today")
    adr: float = Field(..., description="Average Daily Rate today")
    revpar: float = Field(..., description="Revenue Per Available Room today")
    available_rooms: int = Field(..., description="Rooms available today")
    total_rooms: int
    occupied_rooms: int
    demand_index: float = Field(..., description="Current demand index (0–100)")
    compset_adr: float | None = Field(None, description="Competitive set ADR")
    demand_trend: list[DemandPoint] = Field(
        default_factory=list, description="30-day rolling demand trend"
    )
    # Extension fields – populated by future AI engines
    forecasted_occupancy: float | None = Field(
        None, description="ML-forecasted occupancy % for tomorrow"
    )
    recommended_rate: float | None = Field(
        None, description="AI-optimised recommended rate"
    )
    ai_insight: str | None = Field(None, description="Natural-language AI insight")


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    timestamp: datetime
