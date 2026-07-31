"""
Rule-Based Ancillary Revenue Recommendation Engine.

Orchestration pipeline
──────────────────────
1. build_context  – load hotel metrics, events, forecast from DB
2. load_catalog   – get active ancillary products
3. eligibility    – filter ineligible products, log suppression reasons
4. pricing        – compute recommended price per eligible product
5. propensity     – score conversion likelihood per product × context
6. scoring        – compute composite opportunity score
7. rank & limit   – sort by score descending, return top N

All business logic lives in the sub-services (eligibility, pricing,
propensity, scoring).  This class is the thin orchestration layer.

Guardrails (configurable, not hardcoded)
────────────────────────────────────────
max_ancillary_price_increase_pct     : 20.0
max_ancillary_price_decrease_pct     : 15.0
minimum_margin_pct                   : 25.0
maximum_offer_count                  : 5
minimum_propensity_threshold         : 0.10
maximum_capacity_utilization_for_promotion: 0.90
suppress_at_capacity_pct             : 0.95
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from app.models.demand_event import DemandEvent
from app.repositories.event_repository import EventRepository
from app.repositories.hotel_repository import HotelRepository
from app.repositories.metrics_repository import MetricsRepository
from app.schemas.ancillaries import (
    AncillaryContext,
    AncillaryProduct,
    AncillaryRecommendation,
    AncillaryRecommendationResponse,
    AncillaryRecommendationSummary,
    GuestPersona,
)
from app.services.ancillaries.base import AncillaryRecommendationService
from app.services.ancillaries.catalog import AncillaryCatalogService
from app.services.ancillaries.eligibility import (
    EligibilityGuardrails,
    check_eligibility,
)
from app.services.ancillaries.personas import PERSONAS
from app.services.ancillaries.pricing import PricingGuardrails, compute_recommended_price
from app.services.ancillaries.propensity import PropensityScoringService
from app.services.ancillaries.scoring import score_opportunity
from app.services.forecasting.base import ForecastService

logger = logging.getLogger(__name__)

_HISTORY_WINDOW: int = 90


@dataclass(frozen=True)
class AncillaryGuardrails:
    """Full guardrail config consumed by the engine."""

    max_ancillary_price_increase_pct: float = 20.0
    max_ancillary_price_decrease_pct: float = 15.0
    minimum_margin_pct: float = 25.0
    maximum_offer_count: int = 5
    minimum_propensity_threshold: float = 0.10
    maximum_capacity_utilization_for_promotion: float = 0.90
    suppress_at_capacity_pct: float = 0.95
    day_use_room_max_occupancy: float = 88.0

    @property
    def pricing(self) -> PricingGuardrails:
        return PricingGuardrails(
            max_ancillary_price_increase_pct=self.max_ancillary_price_increase_pct,
            max_ancillary_price_decrease_pct=self.max_ancillary_price_decrease_pct,
        )

    @property
    def eligibility(self) -> EligibilityGuardrails:
        return EligibilityGuardrails(
            suppress_at_capacity_pct=self.suppress_at_capacity_pct,
            maximum_capacity_utilization_for_promotion=self.maximum_capacity_utilization_for_promotion,
            minimum_margin_pct=self.minimum_margin_pct,
            day_use_room_max_occupancy=self.day_use_room_max_occupancy,
        )


_DEFAULT_GUARDRAILS = AncillaryGuardrails()


class RuleBasedAncillaryRecommendationService(AncillaryRecommendationService):
    """
    Deterministic rule-based ancillary recommendation engine.

    Constructor parameters follow the project's DI pattern.
    All sub-services are injected; no logic duplicated from existing services.
    """

    engine_model: str = "Rule Based Ancillary Engine v1"

    def __init__(
        self,
        hotel_repo: HotelRepository,
        metrics_repo: MetricsRepository,
        event_repo: EventRepository,
        forecast_svc: ForecastService,
        catalog_svc: AncillaryCatalogService,
        guardrails: AncillaryGuardrails = _DEFAULT_GUARDRAILS,
    ) -> None:
        self._hotel_repo = hotel_repo
        self._metrics_repo = metrics_repo
        self._event_repo = event_repo
        self._forecast_svc = forecast_svc
        self._catalog_svc = catalog_svc
        self._guardrails = guardrails
        self._propensity_svc = PropensityScoringService()

    # ── Public interface ──────────────────────────────────────────────────────

    async def generate_recommendations(
        self,
        hotel_id: str,
        as_of: date,
        persona: GuestPersona = GuestPersona.hotel_wide,
        horizon_days: int = 14,
        limit: int = 5,
    ) -> AncillaryRecommendationResponse:

        context = await self._build_context(hotel_id, as_of, persona, horizon_days)
        products = self._catalog_svc.get_active_products()

        recommendations: list[AncillaryRecommendation] = []
        eligible_count = 0

        for product in products:
            eligible, reason = check_eligibility(
                product, context, self._guardrails.eligibility
            )
            if not eligible:
                logger.debug(
                    "Suppressed %s for hotel %s: %s", product.code, hotel_id, reason
                )
                continue

            eligible_count += 1

            # Pricing
            rec_price, price_reason = compute_recommended_price(
                product, context, self._guardrails.pricing
            )

            # Propensity
            propensity = self._propensity_svc.score(product, context)

            # Below propensity threshold → skip
            if propensity < self._guardrails.minimum_propensity_threshold:
                logger.debug(
                    "Propensity below threshold for %s: %.3f", product.code, propensity
                )
                eligible_count -= 1
                continue

            # Scoring
            score, components = score_opportunity(product, context, propensity, rec_price)

            # Financial estimates
            guests = context.estimated_eligible_guests
            conversions = round(guests * propensity, 2)
            revenue = round(conversions * rec_price * context.avg_stay_length, 2)
            margin = round(conversions * (rec_price - product.variable_cost) * context.avg_stay_length, 2)

            price_change_pct = round(
                (rec_price - product.base_price) / product.base_price * 100.0, 1
            )

            # Confidence
            if propensity >= 0.50 and score >= 50.0:
                confidence = "high"
            elif propensity >= 0.25 or score >= 35.0:
                confidence = "medium"
            else:
                confidence = "low"

            # Reason codes + supporting factors
            reason_codes, supporting = self._build_transparency(
                product, context, propensity, rec_price, price_reason
            )

            rec = AncillaryRecommendation(
                id=f"ANC-{hotel_id[:8]}-{as_of.isoformat().replace('-', '')}-{product.code}-0",
                hotel_id=hotel_id,
                rank=0,  # assigned after sorting
                product=product,
                persona=persona,
                base_price=product.base_price,
                recommended_price=rec_price,
                price_change_pct=price_change_pct,
                price_change_reason=price_reason,
                propensity=round(propensity, 4),
                eligible_guests=guests,
                expected_conversions=conversions,
                expected_revenue=revenue,
                expected_margin=margin,
                score=score,
                score_components=components,
                confidence=confidence,
                reason_codes=reason_codes,
                supporting_factors=supporting,
                generated_at=datetime.now(timezone.utc),
            )
            recommendations.append(rec)

        # Sort by score descending, assign ranks, apply limit
        recommendations.sort(key=lambda r: r.score, reverse=True)
        limit = min(limit, self._guardrails.maximum_offer_count)
        recommendations = recommendations[:limit]
        for i, rec in enumerate(recommendations):
            # Pydantic models are immutable; rebuild with updated rank + id
            recommendations[i] = rec.model_copy(
                update={
                    "rank": i + 1,
                    "id": f"ANC-{hotel_id[:8]}-{as_of.isoformat().replace('-', '')}-{rec.product.code}-{i + 1:03d}",
                }
            )

        summary = AncillaryRecommendationSummary(
            eligible_products=eligible_count,
            shown=len(recommendations),
            total_revenue_opportunity=round(
                sum(r.expected_revenue for r in recommendations), 2
            ),
            total_margin_opportunity=round(
                sum(r.expected_margin for r in recommendations), 2
            ),
        )

        return AncillaryRecommendationResponse(
            hotel_id=hotel_id,
            generated_at=datetime.now(timezone.utc),
            engine_model=self.engine_model,
            persona=persona,
            horizon_days=horizon_days,
            summary=summary,
            recommendations=recommendations,
        )

    # ── Context builder ───────────────────────────────────────────────────────

    async def _build_context(
        self,
        hotel_id: str,
        as_of: date,
        persona: GuestPersona,
        horizon_days: int,
    ) -> AncillaryContext:
        hotel = await self._hotel_repo.get_by_id(hotel_id)
        if hotel is None:
            raise ValueError(f"Hotel {hotel_id!r} not found")

        # Latest metrics
        metrics = await self._metrics_repo.get_by_hotel_and_date(hotel_id, as_of)
        if metrics is None:
            metrics = await self._metrics_repo.get_latest(hotel_id)
        if metrics is None:
            raise ValueError(f"No metrics available for hotel {hotel_id!r}")

        current_occ = metrics.occupancy_pct
        demand_level = metrics.demand_index

        # Forecast occupancy (best-effort; fallback to current)
        forecast_occ = current_occ
        try:
            history_start = as_of - timedelta(days=_HISTORY_WINDOW - 1)
            history_records = await self._metrics_repo.get_range(
                hotel_id, history_start, as_of
            )
            history = [(r.date, r.occupancy_pct) for r in history_records]
            if len(history) >= self._forecast_svc.min_history_days:
                points = await self._forecast_svc.forecast(
                    hotel_id=hotel_id,
                    history=history,
                    horizon=horizon_days,
                    origin=as_of,
                )
                if points:
                    forecast_occ = sum(p.occupancy_pct for p in points) / len(points)
        except Exception as exc:
            logger.warning("Forecast unavailable for ancillary context: %s", exc)

        # Events
        active_event_types: list[str] = []
        has_active_event = False
        try:
            forecast_end = as_of + timedelta(days=horizon_days)
            events = await self._event_repo.get_overlapping(
                hotel_id, as_of, forecast_end
            )
            active_event_types = list({e.event_type for e in events})
            has_active_event = bool(events)
        except Exception as exc:
            logger.warning("Event lookup failed for ancillary context: %s", exc)

        # Persona profile
        profile = PERSONAS.get(persona, PERSONAS[GuestPersona.hotel_wide])

        # Scale eligible guests to hotel size (persona profile is for 200-room reference hotel)
        room_scale = hotel.total_rooms / 200.0
        eligible_guests = max(1, round(profile.estimated_eligible_guests * room_scale))

        return AncillaryContext(
            hotel_id=hotel_id,
            as_of=as_of,
            horizon_days=horizon_days,
            total_rooms=hotel.total_rooms,
            current_occupancy=current_occ,
            forecast_occupancy=forecast_occ,
            demand_level=demand_level,
            active_event_types=active_event_types,
            has_active_event=has_active_event,
            persona=persona,
            estimated_eligible_guests=eligible_guests,
            avg_stay_length=profile.avg_stay_length,
            vehicle_flag=profile.vehicle_flag,
            ev_vehicle_flag=profile.ev_vehicle_flag,
            pet_flag=profile.pet_flag,
        )

    # ── Transparency builder ──────────────────────────────────────────────────

    @staticmethod
    def _build_transparency(
        product: AncillaryProduct,
        context: AncillaryContext,
        propensity: float,
        rec_price: float,
        price_reason: str,
    ) -> tuple[list[str], list[str]]:
        reason_codes: list[str] = []
        supporting: list[str] = []

        if propensity >= 0.50:
            reason_codes.append("high_propensity_segment")
        elif propensity >= 0.25:
            reason_codes.append("moderate_propensity")

        if context.has_active_event and product.applicable_event_types:
            reason_codes.append("event_demand_boost")

        if context.forecast_occupancy >= 85:
            reason_codes.append("high_demand_period")
        elif context.forecast_occupancy < 55:
            reason_codes.append("low_demand_stimulation")

        if rec_price != product.base_price:
            reason_codes.append("dynamic_pricing_applied")

        supporting.extend([
            f"Persona: {context.persona.value}",
            f"Estimated eligible guests: {context.estimated_eligible_guests}",
            f"Propensity: {propensity:.0%}",
            f"Forecast occupancy: {context.forecast_occupancy:.1f}%",
            f"Demand index: {context.demand_level:.0f}/100",
        ])
        if context.active_event_types:
            supporting.append(f"Active events: {', '.join(context.active_event_types)}")
        if price_reason and price_reason != "Base price — no adjustment signals":
            supporting.append(f"Pricing: {price_reason}")

        return reason_codes, supporting
