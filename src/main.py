"""FastAPI application initialization."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.core.config import settings
from src.core.logging import setup_logging
from src.core.middleware import (
    APIVersionHeaderMiddleware,
    CorrelationIDMiddleware,
    RequestLoggingMiddleware,
)
from src.db.session import dispose_engine, init_engine
from src.health.router import router as health_router
from src.uptime.router import router as uptime_router
from src.users.router import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan context manager for startup/shutdown events.

    On startup:
    - Configures structlog logging infrastructure
    - Initializes the database engine

    On shutdown:
    - Disposes of the database engine to clean up connections
    """
    # Configure logging on startup
    setup_logging()

    # Initialize database engine on startup
    init_engine()

    yield

    # Dispose of database engine on shutdown
    await dispose_engine()


app = FastAPI(
    redirect_slashes=False,
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    description=settings.app_description
    + "\n\n> All responses include an `X-API-Version` header indicating the current API version.",
    summary=settings.app_summary,
    contact={
        "name": settings.app_contact_name,
        "url": settings.app_contact_url,
        "email": settings.app_contact_email,
    },
    license_info={
        "name": settings.app_license_name,
        "url": settings.app_license_url,
    },
    terms_of_service=settings.app_terms_of_service,
    openapi_tags=[
        {
            "name": "health",
            "description": "Health check and status endpoints",
        },
        {
            "name": "users",
            "description": "User management endpoints",
        },
        {
            "name": "uptime",
            "description": "Service uptime information",
        },
    ],
    swagger_ui_parameters={
        "defaultModelsExpandDepth": -1,
        "tryItOutEnabled": True,
    },
    lifespan=lifespan,
)

# Register middleware (order matters: CorrelationID first, then RequestLogging, then APIVersion)
app.add_middleware(CorrelationIDMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(APIVersionHeaderMiddleware)

# Include health router with empty prefix so endpoint is at /health
app.include_router(health_router)

# Include users router (prefix already set in router.py)
app.include_router(users_router, tags=["users"])

# Include uptime router (prefix already set in router.py)
app.include_router(uptime_router, tags=["uptime"])
