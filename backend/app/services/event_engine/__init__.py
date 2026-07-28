"""
Event engine package.

Provides the EventEngineService ABC and its rule-based implementation.
The engine is the *composition layer* that owns the end-to-end logic of:

    1. Translating a raw DemandEvent into a per-day uplift using a type-aware
       impact formula (EventImpactService).
    2. Applying confidence weighting to the resulting uplift.
    3. Propagating model metadata (model name, adjustment model name) to
       the API response schema.

Swap ``RuleBasedEventEngineService`` for an ML implementation by changing
only ``get_event_engine_service()`` in ``app/core/dependencies.py``.
"""
from app.services.event_engine.base import EventEngineService
from app.services.event_engine.rule_based import RuleBasedEventEngineService

__all__ = ["EventEngineService", "RuleBasedEventEngineService"]
