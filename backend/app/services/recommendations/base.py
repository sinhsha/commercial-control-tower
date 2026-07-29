"""
Abstract base class for the Commercial Recommendation Engine.

Architecture
────────────
RecommendationService sits above ForecastService, EventEngineService,
MetricsService, and MarketSignalService.  It consumes their outputs and
converts them into ranked Recommendation objects.

It intentionally has no database writes – recommendations are generated
on-demand (no persistence layer in this iteration).

To replace the rule engine with an ML optimiser:
    1. Create a new class (e.g. OptimiserRecommendationService) that
       implements this interface.
    2. Change get_recommendation_service() in app/core/dependencies.py.
    3. No API, schema, or frontend changes required.

Extension notes for a future optimiser
───────────────────────────────────────
The same inputs (forecast, adjusted forecast, events, metrics, market signals)
can be serialised and sent to an OR-Tools/RL agent or a TimesFM-guided demand
model.  The output contract (RecommendationResponse) is unchanged, so the
frontend and API layer are decoupled from the underlying engine.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from app.schemas.recommendations import RecommendationResponse


class RecommendationService(ABC):
    """
    Pluggable interface for the commercial recommendation engine.

    Attributes
    ----------
    recommendation_model : str
        Human-readable engine name returned in the API response and displayed
        in the dashboard.  Must be defined by each subclass.
    """

    recommendation_model: str

    @abstractmethod
    async def generate_recommendations(
        self,
        hotel_id: str,
        as_of: date,
        horizon_days: int = 14,
    ) -> RecommendationResponse:
        """
        Generate ranked commercial recommendations for *hotel_id*.

        Parameters
        ----------
        hotel_id:
            Identifier of the property.
        as_of:
            The date from which the recommendation window starts
            (typically the last historical date or today).
        horizon_days:
            Number of forecast days to consider (default 14).

        Returns
        -------
        RecommendationResponse
            Fully populated response including ranked recommendations,
            summary counts, and model metadata.
        """
        ...
