"""
FastAPI application factory.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings, _bust_settings_cache
from app.core.logging import configure_logging
from app.db.session import create_tables, dispose_engine, _get_session_factory
from app.services.seeder import seed_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Clear the lru_cache so .env is re-read on every (re)start
    _bust_settings_cache()
    settings = get_settings()
    logger = logging.getLogger(__name__)

    logger.info("Starting up %s v%s", settings.app_name, settings.app_version)
    await create_tables()
    async with _get_session_factory()() as session:
        await seed_database(session)
    logger.info("Ready.")

    yield

    logger.info("Shutting down.")
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(debug=settings.debug)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "AI-Powered Hotel Commercial Control Tower API. "
            "Provides occupancy, ADR, RevPAR, demand trend, and extensible "
            "AI forecast/optimisation endpoints."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(api_router)

    # ── Root ──────────────────────────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    async def root():
        return {"message": f"Welcome to {settings.app_name}", "docs": "/docs"}

    return app


app = create_app()
