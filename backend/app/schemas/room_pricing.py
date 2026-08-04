"""
Pydantic schemas for the Dynamic Room Pricing & Inventory Optimization engine.

All models used by:
    - RoomPricingService (service layer)
    - GET /hotels/{id}/room-pricing (API layer)
    - Frontend (serialised JSON)
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class RoomTypePricingRecommendation(BaseModel):
    room_type_id: str
    code: str
    display_name: str
    room_rank: int
    capacity: int
    inventory_count: int
    current_available: int
    current_price: float
    recommended_price: float
    price_change_pct: float
    minimum_price: float
    maximum_price: float
    demand_multiplier: float
    scarcity_multiplier: float
    competitor_multiplier: float
    premium_factor: float
    confidence: Literal["high", "medium", "low"]
    reason_codes: list[str] = Field(default_factory=list)
    supporting_factors: list[str] = Field(default_factory=list)
    guardrails_applied: list[str] = Field(default_factory=list)
    protection_status: Literal["open", "protected", "hold", "closed"]
    upgrade_recommendation: str | None = None
    los_recommendation: str | None = None  # "min_2", "min_3", "close_arrival", "open_arrival", None


class RoomPricingResponse(BaseModel):
    hotel_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    as_of_date: date
    forecast_occupancy_pct: float
    competitor_adr: float
    active_events: list[dict] = Field(default_factory=list)
    recommendations: list[RoomTypePricingRecommendation]
    # Projected KPIs
    projected_adr: float
    projected_revpar: float
    projected_room_revenue: float
    projected_occupancy_pct: float
    projected_revenue_opportunity: float


class RoomCalendarDay(BaseModel):
    date: date
    recommended_price: float
    current_price: float
    price_change_pct: float
    confidence: str
    forecast_occupancy_pct: float
    protection_status: str


class RoomTypeCalendar(BaseModel):
    room_type_id: str
    code: str
    display_name: str
    room_rank: int
    days: list[RoomCalendarDay]


class RoomCalendarResponse(BaseModel):
    hotel_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    horizon_days: int
    room_types: list[RoomTypeCalendar]


class InventoryStatus(BaseModel):
    room_type_id: str
    code: str
    display_name: str
    room_rank: int
    inventory_count: int
    sold: int
    remaining: int
    occupancy_pct: float
    protection_status: str
    upgrade_eligible: bool
    revenue_at_risk: float


class InventoryResponse(BaseModel):
    hotel_id: str
    as_of_date: date
    total_rooms: int
    total_sold: int
    total_available: int
    overall_occupancy_pct: float
    room_types: list[InventoryStatus]
