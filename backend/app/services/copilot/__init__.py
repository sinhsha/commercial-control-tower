"""Copilot service package."""
from app.services.copilot.base import CopilotService
from app.services.copilot.openai_service import OpenAICopilotService

__all__ = ["CopilotService", "OpenAICopilotService"]
