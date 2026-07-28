"""
Abstract base class for event-impact engines.

The contract: given a list of active DemandEvents and a baseline
ForecastPoint for a specific date, return a (possibly zero) occupancy
uplift and a human-readable explanation.

Separation of concerns
─────────────────────
EventImpactService NEVER modifies ForecastService or its outputs.
Instead, the adjusted-forecast endpoint composes the two:

    baseline = ForecastService.forecast(...)
    adjusted = [apply_event_impact(p, events) for p in baseline]

This means ForecastService implementations (Seasonal Baseline, TimesFM, …)
remain pure and unit-testable without any knowledge of events.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from app.models.demand_event import DemandEvent
from app.schemas.events import EventInfluence


class EventImpactService(ABC):
    """
    Pluggable interface for translating demand events into forecast uplifts.

    Replace DefaultEventImpactService with an ML-based implementation by
    changing only the factory in app/core/dependencies.py.
    """

    @abstractmethod
    def compute_uplift(
        self,
        forecast_date: date,
        event: DemandEvent,
        hotel_total_rooms: int,
        days_until_event: int,
    ) -> EventInfluence | None:
        """
        Return an EventInfluence describing this event's impact on
        ``forecast_date``, or None if the event does not affect that date.

        Parameters
        ----------
        forecast_date:
            The date for which uplift is being computed.
        event:
            The demand event to evaluate.
        hotel_total_rooms:
            Hotel room capacity, used to scale per-attendee impact.
        days_until_event:
            Days from today (the forecast origin) until the event starts.
            Used for proximity discounting.
        """
        ...
