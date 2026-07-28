"""
Abstract base class for the Event Engine.

The EventEngine is a higher-level composition layer that orchestrates:
    - Fetching active events for a forecast window
    - Delegating per-event uplift calculation to EventImpactService
    - Applying event confidence weighting to the final uplift
    - Returning a structured AdjustedForecastDay for each date

Unlike EventImpactService (which handles a single event × single date),
EventEngineService handles the full list of events across all forecast dates.

Swap the implementation by changing only get_event_engine_service() in
app/core/dependencies.py.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.demand_event import DemandEvent
from app.schemas.events import AdjustedForecastDay
from app.schemas.forecast import ForecastPoint


class EventEngineService(ABC):
    """
    Pluggable interface for the event adjustment engine.

    Implementations receive the full baseline forecast and the list of
    active events, and return one AdjustedForecastDay per forecast date.

    Attributes
    ----------
    engine_name : str
        Human-readable name returned in the API response's ``adjustment_model``
        field.  Must be defined by each implementation.
    """

    engine_name: str

    @abstractmethod
    def apply(
        self,
        hotel_id: str,
        hotel_total_rooms: int,
        forecast_origin_date: object,  # datetime.date
        baseline: list[ForecastPoint],
        events: list[DemandEvent],
    ) -> list[AdjustedForecastDay]:
        """
        Apply event signals to the baseline forecast.

        Parameters
        ----------
        hotel_id:
            UUID of the hotel being forecast (for logging/tracing).
        hotel_total_rooms:
            Room inventory used in capacity-ratio calculations.
        forecast_origin_date:
            The date from which the forecast was projected (i.e. *today*
            in the forecast timeline, the last day of historical data).
        baseline:
            Ordered list of ForecastPoint objects produced by ForecastService.
        events:
            Active DemandEvents that overlap the forecast window.

        Returns
        -------
        list[AdjustedForecastDay]
            One entry per baseline point; same ordering as ``baseline``.
        """
        ...
