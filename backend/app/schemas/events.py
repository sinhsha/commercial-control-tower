from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


EventType = Literal[
    "convention",
    "concert",
    "sports",
    "weather_disruption",
    "flight_disruption",
    "local_festival",
    "holiday",
    "cruise_arrival",
]

EventStatus = Literal["active", "cancelled", "completed"]


class DemandEventResponse(BaseModel):
    """Read-only event shape returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    hotel_id: str
    name: str
    event_type: str
    start_date: date
    end_date: date
    distance_miles: float
    expected_attendance: int
    impact_strength: float
    confidence: float
    status: str


class CreateDemandEventRequest(BaseModel):
    """Payload for POST /hotels/{id}/events."""

    name: str = Field(..., min_length=2, max_length=200)
    event_type: EventType
    start_date: date
    end_date: date
    distance_miles: float = Field(0.0, ge=0.0, le=500.0)
    expected_attendance: int = Field(0, ge=0)
    impact_strength: float = Field(0.7, ge=0.0, le=1.0)
    confidence: float = Field(0.8, ge=0.0, le=1.0)
    status: EventStatus = "active"

    @model_validator(mode="after")
    def end_after_start(self) -> "CreateDemandEventRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class EventListResponse(BaseModel):
    total: int
    items: list[DemandEventResponse]


# ── Adjusted forecast ─────────────────────────────────────────────────────────


class EventInfluence(BaseModel):
    """A single event that contributed uplift to a forecast date."""

    event_id: str
    event_name: str
    event_type: str
    uplift_points: float = Field(..., description="Occupancy percentage points added by this event")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Engine confidence in this uplift (0–1)")
    explanation: str = Field(..., description="Human-readable one-line explanation")


class AdjustedForecastDay(BaseModel):
    """
    One day in the event-adjusted forecast.

    Carries both the baseline and the event-adjusted occupancy so the
    frontend can render both series from a single response.
    Field names match the agreed API spec:
        date, baseline, adjusted, uplift, confidence_low, confidence_high, reasons
    """

    date: date
    baseline: float = Field(..., ge=0.0, le=100.0, description="Baseline occupancy %")
    adjusted: float = Field(..., ge=0.0, le=100.0, description="Event-adjusted occupancy %")
    uplift: float = Field(..., description="Net uplift = adjusted − baseline (can be negative)")
    confidence_low: float = Field(..., ge=0.0, le=100.0, description="Lower bound of 80% CI")
    confidence_high: float = Field(..., ge=0.0, le=100.0, description="Upper bound of 80% CI")
    reasons: list[str] = Field(default_factory=list, description="Human-readable event names/reasons")
    # Full influence objects for frontend drill-down (not in the minimal spec but backwards-compatible)
    influences: list[EventInfluence] = Field(default_factory=list)


# Legacy alias kept for backwards-compatibility (tests, old imports)
AdjustedForecastPoint = AdjustedForecastDay


class AdjustedForecastResponse(BaseModel):
    """
    Full response for GET /hotels/{id}/forecast/adjusted.

    Matches the agreed spec:
    {
        "model": "Seasonal Baseline",
        "adjustment_model": "Rule Based Event Engine",
        "days": [{ "date": ..., "baseline": 74.3, "adjusted": 82.8,
                   "uplift": 8.5, "confidence_low": ..., "confidence_high": ...,
                   "reasons": ["Comic Con", "Weekend demand"] }]
    }
    """

    model_config = {"protected_namespaces": ()}

    hotel_id: str
    model: str = Field(..., description="Name of the baseline forecasting model")
    adjustment_model: str = Field(..., description="Name of the event-adjustment engine")
    origin_date: date
    horizon: int
    days: list[AdjustedForecastDay]
