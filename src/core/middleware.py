"""ASGI middleware for API versioning headers."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.core.config import settings


class APIVersionHeaderMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that injects X-API-Version header into responses."""

    async def dispatch(self, request: Request, call_next: callable) -> Response:
        """
        Process request and add version header to response.

        Args:
            request: The incoming HTTP request.
            call_next: Callable to process the request and get the response.

        Returns:
            Response with X-API-Version header added.
        """
        response = await call_next(request)
        response.headers["X-API-Version"] = settings.app_version
        return response
