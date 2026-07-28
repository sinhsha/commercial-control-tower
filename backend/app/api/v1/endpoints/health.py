from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.schemas.hotel import HealthResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HealthResponse:
    """Returns service health including database connectivity."""
    try:
        await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        db_status = "error"

    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        version=settings.app_version,
        database=db_status,
        timestamp=datetime.now(timezone.utc),
    )
