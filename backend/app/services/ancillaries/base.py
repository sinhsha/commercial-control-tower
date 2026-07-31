"""
Abstract base class for the Ancillary Revenue Recommendation Engine.

Architecture
────────────
AncillaryRecommendationService sits above the catalog, eligibility,
pricing, propensity, and scoring sub-services.  It consumes hotel data
from existing repositories and produces AncillaryRecommendationResponse.

To replace the rule engine with an ML model:
    1. Create a new class (e.g. MLAncillaryRecommendationService) that
       implements this interface.
    2. Change get_ancillary_recommendation_service() in app/core/dependencies.py.
    3. No API, schema, or frontend changes required.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from app.schemas.ancillaries import (
    AncillaryRecommendationResponse,
    GuestPersona,
)


class AncillaryRecommendationService(ABC):
    """
    Pluggable interface for the ancillary revenue recommendation engine.

    Attributes
    ----------
    engine_model : str
        Human-readable engine name returned in the API response.
    """

    engine_model: str

    @abstractmethod
    async def generate_recommendations(
        self,
        hotel_id: str,
        as_of: date,
        persona: GuestPersona = GuestPersona.hotel_wide,
        horizon_days: int = 14,
        limit: int = 5,
    ) -> AncillaryRecommendationResponse:
        """
        Generate ranked ancillary recommendations for *hotel_id*.

        Parameters
        ----------
        hotel_id:
            Identifier of the property.
        as_of:
            The date from which the recommendation window starts.
        persona:
            Guest persona filter (default: hotel_wide = all guests).
        horizon_days:
            Number of days to consider (default 14).
        limit:
            Maximum number of recommendations to return (default 5).

        Returns
        -------
        AncillaryRecommendationResponse
            Fully populated response including ranked recommendations,
            summary counts, and engine metadata.
        """
        ...
