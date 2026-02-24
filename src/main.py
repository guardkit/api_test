"""FastAPI application initialization."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.core.config import settings
from src.core.middleware import APIVersionHeaderMiddleware
from src.health.router import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan context manager for startup/shutdown events.

    Currently a no-op, but provides the pattern for future startup/shutdown logic.
    """
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    description=settings.app_description + "\n\n> All responses include an `X-API-Version` header indicating the current API version.",
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
    ],
    swagger_ui_parameters={
        "defaultModelsExpandDepth": -1,
        "tryItOutEnabled": True,
    },
    lifespan=lifespan,
)

# Register middleware
app.add_middleware(APIVersionHeaderMiddleware)

# Include health router with empty prefix so endpoint is at /health
app.include_router(health_router)
