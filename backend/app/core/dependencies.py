"""
Dependency-injection container.

Each service is exposed as a FastAPI dependency factory so callsites
never instantiate services directly.  Swap an implementation by
changing the factory – no callsite modifications required.

To replace the forecasting engine (e.g. with TimesFMForecastService):
  Change only `get_forecast_service` to return the new implementation.
  The endpoint, schema, and frontend are unaffected.

To replace the event-adjustment engine (e.g. with MLEventEngineService):
  Change only `get_event_engine_service` to return the new implementation.

To replace the recommendation engine (e.g. with OptimiserRecommendationService):
  Change only `get_recommendation_service` to return the new implementation.
  The API, schemas, and frontend are unaffected.
"""
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.repositories.hotel_repository import HotelRepository
from app.repositories.metrics_repository import MetricsRepository
from app.repositories.event_repository import EventRepository
from app.services.hotel_service import HotelService
from app.services.metrics_service import MetricsService
from app.services.forecasting.base import ForecastService
from app.services.forecasting.seasonal_baseline import SeasonalBaselineForecastService
from app.services.events.base import EventImpactService
from app.services.events.default_impact import DefaultEventImpactService
from app.services.event_engine.base import EventEngineService
from app.services.event_engine.rule_based import RuleBasedEventEngineService
from app.services.market_signals.base import MarketSignalService
from app.services.market_signals.mock import MockMarketSignalService
from app.services.recommendations.base import RecommendationService
from app.services.recommendations.rule_based import RuleBasedRecommendationService
from app.services.ancillaries.base import AncillaryRecommendationService
from app.services.ancillaries.catalog import AncillaryCatalogService, SeededAncillaryCatalogService
from app.services.ancillaries.rule_based import RuleBasedAncillaryRecommendationService
from app.services.copilot.base import CopilotService
from app.services.copilot.openai_service import OpenAICopilotService
# ── Enterprise Forecasting Platform ──────────────────────────────────────────
from app.services.forecasting.model_registry import ForecastModelRegistry, get_default_registry
from app.services.forecasting.evaluation import ForecastEvaluationService
from app.services.forecasting.governance import ForecastGovernanceService
from app.services.forecasting.comparison import ForecastComparisonService
from app.services.forecasting.auto_selector import AutoModelSelector
from app.services.forecasting.timesfm_service import TimesFMForecastService
from app.services.forecasting.manager import ForecastManagerService


# ── Repositories ─────────────────────────────────────────────────────────────

def get_hotel_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HotelRepository:
    return HotelRepository(session)


def get_metrics_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MetricsRepository:
    return MetricsRepository(session)


# ── Services ──────────────────────────────────────────────────────────────────

def get_hotel_service(
    repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
) -> HotelService:
    return HotelService(repo)


def get_metrics_service(
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    metrics_repo: Annotated[MetricsRepository, Depends(get_metrics_repository)],
) -> MetricsService:
    return MetricsService(hotel_repo, metrics_repo)


def get_forecast_service() -> ForecastService:
    """
    Factory for the active forecasting implementation.

    Swap this return value to change the engine project-wide:
        return TimesFMForecastService()
    """
    return SeasonalBaselineForecastService()


def get_event_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EventRepository:
    return EventRepository(session)


def get_event_impact_service() -> EventImpactService:
    """
    Factory for the active event-impact engine.

    Swap this return value to change the event-impact model project-wide:
        return MLEventImpactService()
    """
    return DefaultEventImpactService()


def get_event_engine_service(
    impact_svc: Annotated[EventImpactService, Depends(get_event_impact_service)],
) -> EventEngineService:
    """
    Factory for the active event-adjustment engine.

    The engine is a composition layer on top of EventImpactService.
    Swap this return value to change the adjustment engine project-wide:
        return MLEventEngineService(impact_svc)
    """
    return RuleBasedEventEngineService(impact_svc)


def get_market_signal_service() -> MarketSignalService:
    """
    Factory for the active market-signal provider.

    Swap this return value to use a real rate-shopping feed:
        return LiveRateShopMarketSignalService(api_key=settings.rate_shop_api_key)
    """
    return MockMarketSignalService()


def get_recommendation_service(
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    metrics_repo: Annotated[MetricsRepository, Depends(get_metrics_repository)],
    event_repo: Annotated[EventRepository, Depends(get_event_repository)],
    forecast_svc: Annotated[ForecastService, Depends(get_forecast_service)],
    event_engine_svc: Annotated[EventEngineService, Depends(get_event_engine_service)],
    market_signal_svc: Annotated[MarketSignalService, Depends(get_market_signal_service)],
) -> RecommendationService:
    """
    Factory for the active commercial recommendation engine.

    Swap this return value to change the engine project-wide:
        return OptimiserRecommendationService(...)
    """
    return RuleBasedRecommendationService(
        hotel_repo=hotel_repo,
        metrics_repo=metrics_repo,
        event_repo=event_repo,
        forecast_svc=forecast_svc,
        event_engine_svc=event_engine_svc,
        market_signal_svc=market_signal_svc,
    )


# ── Ancillary Revenue Engine ──────────────────────────────────────────────────

def get_ancillary_catalog_service() -> AncillaryCatalogService:
    """
    Factory for the active ancillary catalog provider.

    Swap this return value to use a DB-backed catalog:
        return DBBackedAncillaryCatalogService(session)
    """
    return SeededAncillaryCatalogService()


def get_ancillary_recommendation_service(
    hotel_repo: Annotated[HotelRepository, Depends(get_hotel_repository)],
    metrics_repo: Annotated[MetricsRepository, Depends(get_metrics_repository)],
    event_repo: Annotated[EventRepository, Depends(get_event_repository)],
    forecast_svc: Annotated[ForecastService, Depends(get_forecast_service)],
    catalog_svc: Annotated[AncillaryCatalogService, Depends(get_ancillary_catalog_service)],
) -> AncillaryRecommendationService:
    """
    Factory for the active ancillary recommendation engine.

    Swap this return value to change the engine project-wide:
        return MLAncillaryRecommendationService(...)
    """
    return RuleBasedAncillaryRecommendationService(
        hotel_repo=hotel_repo,
        metrics_repo=metrics_repo,
        event_repo=event_repo,
        forecast_svc=forecast_svc,
        catalog_svc=catalog_svc,
    )


# ── Copilot / Grounded Explanation Service ────────────────────────────────────

def get_copilot_service() -> CopilotService:
    """
    Factory for the active copilot / grounded LLM explanation service.

    Swap this return value to change the LLM provider project-wide:
        return AnthropicCopilotService()
        return WatsonXCopilotService()

    When OPENAI_API_KEY is not configured or copilot_enabled=false,
    OpenAICopilotService automatically degrades to structured fallback text.
    All other dashboard panels are unaffected.
    """
    return OpenAICopilotService()


# ── Enterprise Forecasting Platform ───────────────────────────────────────────

def get_forecast_model_registry() -> ForecastModelRegistry:
    """Returns the module-level singleton model registry."""
    return get_default_registry()


def get_forecast_evaluation_service() -> ForecastEvaluationService:
    """Evaluation service backed by the SeasonalBaseline model."""
    return ForecastEvaluationService(SeasonalBaselineForecastService())


def get_forecast_governance_service() -> ForecastGovernanceService:
    """Governance service with default thresholds from settings."""
    settings = get_settings()
    return ForecastGovernanceService(
        fallback_svc=SeasonalBaselineForecastService(),
        max_jump_pp=settings.forecast_governance_max_jump_pp,
        min_history_days=settings.forecast_governance_min_history_days,
    )


def get_forecast_comparison_service(
    registry: Annotated[ForecastModelRegistry, Depends(get_forecast_model_registry)],
    eval_svc: Annotated[ForecastEvaluationService, Depends(get_forecast_evaluation_service)],
) -> ForecastComparisonService:
    """Comparison service for all registered models."""
    return ForecastComparisonService(
        registry=registry,
        baseline_eval_svc=eval_svc,
        timesfm_eval_svc=None,  # TimesFM uses same evaluation pathway via fallback
    )


def get_auto_model_selector(
    comparison_svc: Annotated[ForecastComparisonService, Depends(get_forecast_comparison_service)],
) -> AutoModelSelector:
    """Auto model selector with TTL cache."""
    settings = get_settings()
    return AutoModelSelector(
        comparison_svc=comparison_svc,
        ttl_seconds=settings.forecast_auto_selector_ttl_seconds,
        window="last_30",
    )


def get_forecast_manager_service(
    governance_svc: Annotated[ForecastGovernanceService, Depends(get_forecast_governance_service)],
    auto_selector: Annotated[AutoModelSelector, Depends(get_auto_model_selector)],
    eval_svc: Annotated[ForecastEvaluationService, Depends(get_forecast_evaluation_service)],
    registry: Annotated[ForecastModelRegistry, Depends(get_forecast_model_registry)],
) -> ForecastManagerService:
    """Orchestrating manager service."""
    settings = get_settings()
    baseline_svc = SeasonalBaselineForecastService()
    timesfm_svc = TimesFMForecastService(
        timeout_seconds=settings.timesfm_timeout_seconds,
        device=settings.timesfm_device,
        repo_id=settings.timesfm_model_name,
        context_length=settings.timesfm_context_length,
    )
    return ForecastManagerService(
        provider=settings.forecast_provider,
        registry=registry,
        baseline_svc=baseline_svc,
        timesfm_svc=timesfm_svc,
        governance_svc=governance_svc,
        auto_selector=auto_selector,
        eval_svc=eval_svc,
    )
