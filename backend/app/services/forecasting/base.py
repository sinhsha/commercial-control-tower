"""
Abstract base class for occupancy forecasting engines.

To add a new implementation (e.g. TimesFMForecastService):
  1. Create a new module under app/services/forecasting/
  2. Subclass ForecastService and implement `forecast()`
  3. Change the factory in app/core/dependencies.py to return the new class
  4. No endpoint, schema, or frontend changes required.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from app.schemas.forecast import ForecastPoint


class ForecastService(ABC):
    """
    Pluggable forecasting interface.

    Implementations must be stateless with respect to a single `forecast()`
    call so they are safe to use as per-request FastAPI dependencies.
    """

    #: Human-readable name surfaced in API responses and the UI.
    model_name: str

    #: Minimum number of historical days required to produce a forecast.
    min_history_days: int

    @abstractmethod
    async def forecast(
        self,
        hotel_id: str,
        history: list[tuple[date, float]],
        horizon: int,
        origin: date,
    ) -> list[ForecastPoint]:
        """
        Produce an occupancy forecast.

        Parameters
        ----------
        hotel_id:
            Identifier of the property (informational; some implementations
            may use it for model selection).
        history:
            Ordered list of ``(date, occupancy_pct)`` tuples covering the
            available historical window.  The last entry is the most recent
            observation.
        horizon:
            Number of future days to forecast (1–90).
        origin:
            The date *after* which forecasts begin (i.e. ``origin + 1 day``
            is the first forecast date).

        Returns
        -------
        list[ForecastPoint]
            Exactly ``horizon`` items in ascending date order.
        """
        ...
