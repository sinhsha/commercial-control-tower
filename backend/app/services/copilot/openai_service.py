"""
OpenAI-backed Copilot / Grounded Explanation Service.

Architecture
────────────
This service composes prompts from the structured grounding payloads produced
by the deterministic engines, calls the OpenAI Chat Completions API, and
returns the model's response wrapped in a CopilotResponse.

Grounding contract (MUST NOT be violated)
──────────────────────────────────────────
• Every system prompt explicitly instructs the model to use ONLY the provided
  structured data as its factual basis.
• The model is told that demand-event rationale is already shown to the user
  in a separate deterministic panel — it must NOT regenerate or overwrite it.
• The model is told to explain downstream commercial/ancillary actions in
  plain business English, referencing event facts only as context.
• No PII, no user-controlled free-text reaches the LLM except the copilot
  question field — which is length-limited (500 chars) and sanitised.

Fallback behaviour
──────────────────
If OPENAI_API_KEY is not configured, or the API call fails, the service
returns a CopilotResponse with status=unavailable/error and a structured
fallback explanation built from the grounding data alone.  The UI handles
this gracefully — all other dashboard panels continue working.

To swap to another LLM provider (Anthropic, WatsonX, etc.):
    1. Subclass CopilotService and implement the four abstract methods.
    2. Change get_copilot_service() in app/core/dependencies.py.
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings
from app.schemas.copilot import (
    AncillaryGrounding,
    CommercialGrounding,
    CopilotQuestion,
    CopilotResponse,
    CopilotStatus,
    CopilotSurface,
    ExecutiveSummaryGrounding,
)
from app.services.copilot.base import CopilotService

logger = logging.getLogger(__name__)

# ── System prompt base ─────────────────────────────────────────────────────────

_BASE_SYSTEM = """You are a Revenue Management Copilot for a hotel commercial control tower.
You ONLY use the structured data provided in the user message as your factual basis.
You do NOT invent facts, percentages, or financial figures not present in the context.
You do NOT regenerate, duplicate, or overwrite the existing demand-event adjustment
rationale — that is shown separately and is already explained to the user.
You MAY reference event facts as context when explaining downstream commercial actions.
Respond in plain, professional business English.
Be concise: 2–4 sentences unless asked for more.
Do not use markdown bullet lists unless the question explicitly asks for them.
Always label financial figures as estimates."""

# ── Prompt builders ────────────────────────────────────────────────────────────


def _fmt_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return "No active demand events."
    parts = []
    for e in events[:4]:
        parts.append(
            f"{e.get('name','?')} ({e.get('event_type','?')}, "
            f"{e.get('attendance',0):,} attendees, "
            f"{e.get('distance_miles',0):.1f} mi away)"
        )
    return "; ".join(parts)


def _commercial_prompt(g: CommercialGrounding) -> str:
    return f"""Hotel: {g.hotel_name}
As-of date: {g.as_of_date}
Current occupancy: {g.current_occupancy_pct:.1f}%
Forecast occupancy: {g.forecast_occupancy_pct:.1f}%
Current ADR: ${g.current_adr:.0f}  Competitor ADR: ${g.competitor_adr:.0f}
Booking pace: {g.booking_pace_index:.2f}x normal
Active demand signals: {_fmt_events(g.active_events)}

Commercial recommendation: {g.recommendation_title}
Action: {g.recommendation_action}  Category: {g.recommendation_category}
{"Current value: " + str(g.current_value) + " " + g.unit if g.current_value else ""}
{"Recommended value: " + str(g.recommended_value) + " " + g.unit if g.recommended_value else ""}
Estimated revenue impact: ${g.expected_revenue_impact:,.0f} (estimate)
Priority: {g.priority}  Confidence: {g.confidence}
Reason codes: {", ".join(g.reason_codes)}
Supporting factors: {"; ".join(g.supporting_factors)}
Risk flags: {"; ".join(g.risk_flags) if g.risk_flags else "None"}

In 2–4 sentences, explain to a revenue manager why this action is recommended
and what business outcome it supports. Reference the demand context only as
supporting evidence — do not re-explain the demand-event rationale."""


def _ancillary_prompt(g: AncillaryGrounding) -> str:
    components_str = "  ".join(
        f"{k}={v:.1f}" for k, v in (g.score_components or {}).items()
    )
    return f"""Hotel forecast occupancy: {g.forecast_occupancy_pct:.1f}%
Active demand signals: {_fmt_events(g.active_events)}
Guest persona: {g.persona}

Ancillary offer: {g.ancillary_name} (rank #{g.rank}, {g.ancillary_category})
Base price: ${g.base_price:.0f}  Recommended price: ${g.recommended_price:.0f}  ({g.price_change_pct:+.1f}%)
Estimated purchase probability: {g.purchase_probability:.0%}
Estimated incremental revenue: ${g.expected_revenue:,.0f} (estimate)
Estimated margin: ${g.expected_margin:,.0f} (estimate)
Opportunity score: {g.opportunity_score:.0f}/100
Score components: {components_str}
Reason codes: {", ".join(g.reason_codes)}
Supporting factors: {"; ".join(g.supporting_factors)}
Guardrails applied: {"; ".join(g.guardrails_applied) if g.guardrails_applied else "None"}

In 2–3 sentences, explain to a revenue manager why this ancillary offer is ranked
#{g.rank} and why now is the right time to promote it to this guest segment."""


def _executive_prompt(g: ExecutiveSummaryGrounding) -> str:
    return f"""Hotel: {g.hotel_name}
As-of date: {g.as_of_date}
Current occupancy: {g.current_occupancy_pct:.1f}%
Forecast occupancy: {g.forecast_occupancy_pct:.1f}% (uplift: {g.forecast_uplift_pct:+.1f}pp)
Current ADR: ${g.current_adr:.0f}  Competitor ADR: ${g.competitor_adr:.0f}
Active demand signals: {_fmt_events(g.active_events)}
Guest persona context: {g.persona}

Room revenue opportunity: ${g.room_revenue_opportunity:,.0f} (estimate)
Ancillary revenue opportunity: ${g.ancillary_revenue_opportunity:,.0f} (estimate)
Total revenue opportunity: ${g.total_revenue_opportunity:,.0f} (estimate)

Top commercial actions:
{chr(10).join(f"- {a}" for a in g.top_commercial_actions)}

Top ancillary offers:
{chr(10).join(f"- {a}" for a in g.top_ancillary_offers)}

Write a 3–5 sentence executive-level summary for a General Manager or Commercial
Director. Focus on the total revenue opportunity, key demand drivers, and the
integrated room + ancillary strategy. Label financial figures as estimates."""


def _copilot_prompt(g: CopilotQuestion) -> str:
    return f"""Hotel: {g.hotel_name}
As-of date: {g.as_of_date}
Current occupancy: {g.current_occupancy_pct:.1f}%
Forecast occupancy: {g.forecast_occupancy_pct:.1f}%
Current ADR: ${g.current_adr:.0f}  Competitor ADR: ${g.competitor_adr:.0f}
Active demand signals: {_fmt_events(g.active_events)}
Top commercial actions: {"; ".join(g.top_commercial_actions[:3]) or "None"}
Top ancillary offers: {"; ".join(g.top_ancillary_offers[:3]) or "None"}
Room revenue opportunity: ${g.room_revenue_opportunity:,.0f} (estimate)
Ancillary revenue opportunity: ${g.ancillary_revenue_opportunity:,.0f} (estimate)
Guest persona: {g.persona}

Revenue manager question: {g.question}

Answer factually based only on the data above. Be concise and practical."""


# ── Fallback explanation builders (no LLM) ────────────────────────────────────

def _commercial_fallback(g: CommercialGrounding) -> str:
    factors = "; ".join(g.supporting_factors[:3]) if g.supporting_factors else "high demand"
    return (
        f"The '{g.recommendation_title}' action is recommended with {g.confidence} confidence "
        f"because: {factors}. "
        f"Estimated revenue impact: ${g.expected_revenue_impact:,.0f} (estimate). "
        f"Priority: {g.priority}."
    )


def _ancillary_fallback(g: AncillaryGrounding) -> str:
    factors = "; ".join(g.supporting_factors[:2]) if g.supporting_factors else "current demand"
    return (
        f"{g.ancillary_name} is ranked #{g.rank} for the {g.persona} persona. "
        f"Key factors: {factors}. "
        f"Estimated purchase probability {g.purchase_probability:.0%}, "
        f"expected revenue ${g.expected_revenue:,.0f} (estimate)."
    )


def _executive_fallback(g: ExecutiveSummaryGrounding) -> str:
    return (
        f"{g.hotel_name} has a total estimated revenue opportunity of "
        f"${g.total_revenue_opportunity:,.0f} (estimate) — "
        f"${g.room_revenue_opportunity:,.0f} from room actions and "
        f"${g.ancillary_revenue_opportunity:,.0f} from ancillary offers — "
        f"driven by a forecast occupancy of {g.forecast_occupancy_pct:.1f}%."
    )


def _copilot_fallback(g: CopilotQuestion) -> str:
    return (
        f"Based on available data: {g.hotel_name} has forecast occupancy "
        f"{g.forecast_occupancy_pct:.1f}%, ADR ${g.current_adr:.0f}, "
        f"total revenue opportunity ${g.room_revenue_opportunity + g.ancillary_revenue_opportunity:,.0f} (estimate). "
        f"LLM explanation is currently unavailable."
    )


# ── Service implementation ─────────────────────────────────────────────────────


class OpenAICopilotService(CopilotService):
    """
    Grounded explanation service backed by the OpenAI Chat Completions API.

    Degrades gracefully to structured fallback when:
    - OPENAI_API_KEY is not set
    - copilot_enabled = false
    - The API call fails (network error, rate limit, etc.)
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._enabled = settings.copilot_enabled and bool(settings.openai_api_key)
        self._model = settings.openai_model
        self._max_tokens = settings.copilot_max_tokens
        self._client = None

        if self._enabled:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=settings.openai_api_key)
            except ImportError:
                logger.warning("openai package not installed — copilot disabled")
                self._enabled = False

    async def _call(
        self,
        surface: CopilotSurface,
        user_prompt: str,
        fallback: str,
    ) -> CopilotResponse:
        if not self._enabled or self._client is None:
            return CopilotResponse(
                surface=surface,
                status=CopilotStatus.unavailable,
                explanation=fallback,
                fallback_reason="OPENAI_API_KEY not configured or copilot disabled",
            )
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _BASE_SYSTEM},
                    {"role": "user",   "content": user_prompt},
                ],
                max_tokens=self._max_tokens,
                temperature=0.2,   # low temperature → factual, repeatable
            )
            text = resp.choices[0].message.content or fallback
            tokens = resp.usage.total_tokens if resp.usage else 0
            return CopilotResponse(
                surface=surface,
                status=CopilotStatus.ok,
                explanation=text.strip(),
                model_used=self._model,
                tokens_used=tokens,
            )
        except Exception as exc:
            logger.exception("OpenAI copilot call failed: %s", exc)
            return CopilotResponse(
                surface=surface,
                status=CopilotStatus.error,
                explanation=fallback,
                fallback_reason=str(exc),
            )

    async def explain_commercial(self, grounding: CommercialGrounding) -> CopilotResponse:
        return await self._call(
            CopilotSurface.commercial_recommendation,
            _commercial_prompt(grounding),
            _commercial_fallback(grounding),
        )

    async def explain_ancillary(self, grounding: AncillaryGrounding) -> CopilotResponse:
        return await self._call(
            CopilotSurface.ancillary_recommendation,
            _ancillary_prompt(grounding),
            _ancillary_fallback(grounding),
        )

    async def executive_summary(self, grounding: ExecutiveSummaryGrounding) -> CopilotResponse:
        return await self._call(
            CopilotSurface.executive_summary,
            _executive_prompt(grounding),
            _executive_fallback(grounding),
        )

    async def ask(self, grounding: CopilotQuestion) -> CopilotResponse:
        return await self._call(
            CopilotSurface.copilot_question,
            _copilot_prompt(grounding),
            _copilot_fallback(grounding),
        )
