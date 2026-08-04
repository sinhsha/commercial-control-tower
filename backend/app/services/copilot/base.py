"""
Abstract base class for the Copilot / Grounded Explanation Service.

Swap the implementation by changing get_copilot_service() in
app/core/dependencies.py — no endpoint or frontend changes required.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.copilot import (
    AncillaryGrounding,
    CommercialGrounding,
    CopilotQuestion,
    CopilotResponse,
    ExecutiveSummaryGrounding,
)


class CopilotService(ABC):
    """
    Pluggable interface for LLM-powered grounded explanations.

    All implementations receive ONLY structured data that was produced by the
    deterministic engines.  They must never regenerate, replace, or contradict
    the existing ExplainabilityPanel (demand-event / adjusted-forecast rationale).

    Extension notes
    ───────────────
    To swap the LLM provider (e.g. Anthropic, WatsonX):
        1. Subclass CopilotService and implement the four abstract methods.
        2. Change get_copilot_service() in app/core/dependencies.py.
        3. No API, schema, or frontend changes required.
    """

    @abstractmethod
    async def explain_commercial(self, grounding: CommercialGrounding) -> CopilotResponse:
        """
        Generate a concise business explanation for a single commercial
        recommendation (rate change, restriction, package, etc.).

        The explanation MUST be grounded in the supplied structured data.
        It MUST NOT reproduce or contradict the demand-event rationale shown
        in the ExplainabilityPanel — it may reference event facts as context.
        """
        ...

    @abstractmethod
    async def explain_ancillary(self, grounding: AncillaryGrounding) -> CopilotResponse:
        """
        Generate a concise explanation for a single ancillary next-best-offer
        recommendation (parking, spa, meeting room, etc.).
        """
        ...

    @abstractmethod
    async def executive_summary(self, grounding: ExecutiveSummaryGrounding) -> CopilotResponse:
        """
        Generate a 3–5 sentence executive-level total-revenue summary suitable
        for a GM or commercial director, synthesising room and ancillary
        opportunities.
        """
        ...

    @abstractmethod
    async def ask(self, grounding: CopilotQuestion) -> CopilotResponse:
        """
        Answer a free-form revenue manager question, grounded in the full
        commercial context supplied.  The answer must stay factual and
        reference only the provided structured data.
        """
        ...
