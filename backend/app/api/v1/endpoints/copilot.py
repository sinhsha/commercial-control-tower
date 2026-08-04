"""
Copilot / Grounded Explanation endpoints.

These endpoints use the LLM only for:
  1. Commercial recommendation explanations
  2. Ancillary recommendation explanations
  3. Total revenue executive summary
  4. Revenue Manager Copilot Q&A

They do NOT replace, duplicate, or affect the existing demand-event
ExplainabilityPanel — that component is deterministic and unchanged.

The LLM is grounded exclusively with structured data from the deterministic
engines.  No raw user PII or unvalidated input reaches the LLM.

All endpoints degrade gracefully:
  - If the LLM key is not configured → returns structured fallback text
  - If the LLM call fails → returns structured fallback text + error status
  - The rest of the dashboard is never affected
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import (
    get_ancillary_recommendation_service,
    get_copilot_service,
    get_event_repository,
    get_forecast_service,
    get_hotel_repository,
    get_metrics_repository,
    get_recommendation_service,
    get_market_signal_service,
)
from app.repositories.event_repository import EventRepository
from app.repositories.hotel_repository import HotelRepository
from app.repositories.metrics_repository import MetricsRepository
from app.schemas.ancillaries import GuestPersona
from app.schemas.copilot import (
    CopilotAskRequest,
    CopilotQuestion,
    CopilotResponse,
    CopilotStatus,
    CopilotSurface,
    ExplainAncillaryRequest,
    ExplainCommercialRequest,
    ExplainExecutiveSummaryRequest,
)
from app.services.ancillaries.base import AncillaryRecommendationService
from app.services.copilot.base import CopilotService
from app.services.copilot.grounding import (
    ancillary_grounding,
    commercial_grounding,
    executive_summary_grounding,
)
from app.services.forecasting.base import ForecastService
from app.services.market_signals.base import MarketSignalService
from app.services.recommendations.base import RecommendationService

router = APIRouter(prefix="/hotels", tags=["copilot"])
logger = logging.getLogger(__name__)

_HISTORY_WINDOW = 90
_DEFAULT_HORIZON = 14


# ── Helper: build event facts list ────────────────────────────────────────────

async def _event_facts(event_repo: EventRepository, hotel_id: str, origin: date, days: int) -> list[dict]:
    forecast_end = origin + timedelta(days=days)
    events = await event_repo.get_overlapping(hotel_id, origin + timedelta(days=1), forecast_end)
    return [
        {
            "name": e.name,
            "event_type": e.event_type,
            "attendance": e.expected_attendance,
            "distance_miles": e.distance_miles,
            "confidence": e.confidence,
        }
        for e in events
    ]


# ── Helper: resolve origin date ───────────────────────────────────────────────

async def _resolve_origin(
    metrics_repo: MetricsRepository, hotel_id: str, as_of: date | None
) -> date:
    if as_of is not None:
        return as_of
    latest = await metrics_repo.get_latest(hotel_id)
    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No historical data available for this hotel",
        )
    return latest.date


# ── 1. Explain commercial recommendation ──────────────────────────────────────


@router.post(
    "/{hotel_id}/copilot/explain-commercial",
    response_model=CopilotResponse,
    summary="LLM explanation for a commercial recommendation",
    description=(
        "Generates a grounded natural-language explanation for a single commercial "
        "recommendation.  The LLM uses only structured data as its factual basis. "
        "Does NOT replace or regenerate the demand-event ExplainabilityPanel."
    ),
)
async def explain_commercial(
    hotel_id: str,
    body: ExplainCommercialRequest,
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    copilot_svc: Annotated[CopilotService, Depends(get_copilot_service)],
) -> CopilotResponse:
    hotel = await hotel_repo.get_by_id(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    try:
        return await copilot_svc.explain_commercial(body.grounding)
    except Exception as exc:
        logger.exception("Copilot explain-commercial error: %s", exc)
        return CopilotResponse(
            surface=CopilotSurface.commercial_recommendation,
            status=CopilotStatus.error,
            explanation=f"Explanation unavailable: {exc}",
            fallback_reason=str(exc),
        )


# ── 2. Explain ancillary recommendation ───────────────────────────────────────


@router.post(
    "/{hotel_id}/copilot/explain-ancillary",
    response_model=CopilotResponse,
    summary="LLM explanation for an ancillary recommendation",
    description=(
        "Generates a grounded natural-language explanation for a single ancillary "
        "next-best-offer recommendation."
    ),
)
async def explain_ancillary(
    hotel_id: str,
    body: ExplainAncillaryRequest,
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    copilot_svc: Annotated[CopilotService, Depends(get_copilot_service)],
) -> CopilotResponse:
    hotel = await hotel_repo.get_by_id(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    try:
        return await copilot_svc.explain_ancillary(body.grounding)
    except Exception as exc:
        logger.exception("Copilot explain-ancillary error: %s", exc)
        return CopilotResponse(
            surface=CopilotSurface.ancillary_recommendation,
            status=CopilotStatus.error,
            explanation=f"Explanation unavailable: {exc}",
            fallback_reason=str(exc),
        )


# ── 3. Executive summary ──────────────────────────────────────────────────────


@router.get(
    "/{hotel_id}/copilot/executive-summary",
    response_model=CopilotResponse,
    summary="LLM-generated total-revenue executive summary",
    description=(
        "Synthesises room and ancillary revenue opportunities into a 3–5 sentence "
        "executive-level narrative grounded in live structured data."
    ),
)
async def get_executive_summary(
    hotel_id: str,
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    metrics_repo: Annotated[MetricsRepository, Depends(get_metrics_repository)],
    event_repo: Annotated[EventRepository, Depends(get_event_repository)],
    forecast_svc: Annotated[ForecastService, Depends(get_forecast_service)],
    rec_svc: Annotated[RecommendationService, Depends(get_recommendation_service)],
    anc_svc: Annotated[AncillaryRecommendationService, Depends(get_ancillary_recommendation_service)],
    market_svc: Annotated[MarketSignalService, Depends(get_market_signal_service)],
    copilot_svc: Annotated[CopilotService, Depends(get_copilot_service)],
    as_of: date | None = Query(None),
    days: int = Query(_DEFAULT_HORIZON, ge=1, le=90),
    persona: GuestPersona = Query(GuestPersona.hotel_wide),
) -> CopilotResponse:

    hotel = await hotel_repo.get_by_id(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    origin = await _resolve_origin(metrics_repo, hotel_id, as_of)
    metrics = await metrics_repo.get_latest(hotel_id)
    if metrics is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="No metrics available")

    signals = await market_svc.get_signals(hotel_id, hotel_adr=metrics.adr)
    events = await _event_facts(event_repo, hotel_id, origin, days)

    # Generate both engine outputs (graceful degradation if either fails)
    try:
        rec_response = await rec_svc.generate_recommendations(hotel_id, origin, days)
    except Exception:
        from app.schemas.recommendations import RecommendationResponse, RecommendationSummary
        import datetime as _dt
        rec_response = RecommendationResponse(
            hotel_id=hotel_id,
            generated_at=_dt.datetime.now(_dt.timezone.utc),
            forecast_model="",
            adjustment_model="",
            recommendation_model="",
            summary=RecommendationSummary(total=0, critical=0, high=0, medium=0, low=0,
                                          estimated_revenue_opportunity=0.0),
            recommendations=[],
        )

    try:
        anc_response = await anc_svc.generate_recommendations(hotel_id, origin, persona, days, 5)
    except Exception:
        from app.schemas.ancillaries import AncillaryRecommendationResponse, AncillaryRecommendationSummary
        import datetime as _dt
        anc_response = AncillaryRecommendationResponse(
            hotel_id=hotel_id,
            generated_at=_dt.datetime.now(_dt.timezone.utc),
            engine_model="",
            persona=persona,
            horizon_days=days,
            summary=AncillaryRecommendationSummary(eligible_products=0, shown=0,
                                                    total_revenue_opportunity=0.0,
                                                    total_margin_opportunity=0.0),
            recommendations=[],
        )

    # Build forecast occupancy estimate
    history_start = origin - timedelta(days=_HISTORY_WINDOW - 1)
    history_records = await metrics_repo.get_range(hotel_id, history_start, origin)
    forecast_occ = metrics.occupancy_pct
    if len(history_records) >= forecast_svc.min_history_days:
        history = [(r.date, r.occupancy_pct) for r in history_records]
        pts = await forecast_svc.forecast(hotel_id, history, days, origin)
        if pts:
            forecast_occ = sum(p.occupancy_pct for p in pts) / len(pts)

    grounding = executive_summary_grounding(
        hotel_name=hotel.name,
        as_of_date=origin.isoformat(),
        current_occupancy=metrics.occupancy_pct,
        forecast_occupancy=forecast_occ,
        current_adr=metrics.adr,
        competitor_adr=signals.competitor_adr,
        active_events=events,
        rec_response=rec_response,
        anc_response=anc_response,
        persona=persona.value,
    )

    try:
        return await copilot_svc.executive_summary(grounding)
    except Exception as exc:
        logger.exception("Copilot executive-summary error: %s", exc)
        return CopilotResponse(
            surface=CopilotSurface.executive_summary,
            status=CopilotStatus.error,
            explanation=f"Summary unavailable: {exc}",
            fallback_reason=str(exc),
        )


# ── 4. Revenue Manager Copilot Q&A ────────────────────────────────────────────


@router.post(
    "/{hotel_id}/copilot/ask",
    response_model=CopilotResponse,
    summary="Revenue Manager Copilot — free-form question",
    description=(
        "Answers a revenue manager question grounded in the hotel's live commercial "
        "context.  The LLM may not use facts outside the supplied structured data."
    ),
)
async def copilot_ask(
    hotel_id: str,
    body: CopilotAskRequest,
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    copilot_svc: Annotated[CopilotService, Depends(get_copilot_service)],
) -> CopilotResponse:
    hotel = await hotel_repo.get_by_id(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    try:
        return await copilot_svc.ask(body.grounding)
    except Exception as exc:
        logger.exception("Copilot ask error: %s", exc)
        return CopilotResponse(
            surface=CopilotSurface.copilot_question,
            status=CopilotStatus.error,
            explanation=f"Copilot unavailable: {exc}",
            fallback_reason=str(exc),
        )
