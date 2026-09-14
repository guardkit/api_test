"""Application-wide error types, and the one place an error becomes a response.

`docs/API.md` settles the shape of every error body this service returns::

    {"detail": "Error message description"}

Before this module each route translated a database failure by hand, with
``detail=f"Database unavailable: {exc}"``. That put whatever the database
driver happened to say into the response, so two endpoints reported the same
outage with different wording, and connection strings, SQL fragments and
driver class names reached the caller.

The translation happens here instead, once:

* a route that loses the database raises :class:`DatabaseUnavailableError`
  (or lets a SQLAlchemy error escape, which the safety-net handler catches);
* the handler below answers with the documented body — a single ``detail``
  string, identical for every caller and every endpoint, and nothing of the
  underlying error except a server-side log line.

Nothing here is users-specific on purpose: any feature that loses the
database gets the same answer as every other one.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class AppError(Exception):
    """An error the application raises deliberately, with a status attached.

    Subclasses set :attr:`status_code`, :attr:`error_code` and
    :attr:`default_detail`; the registered handler turns an instance into the
    documented error body, so a route raising one never formats a response.

    Attributes:
        status_code: The HTTP status the handler answers with.
        error_code: Stable name for logs and for clients that branch on the
            failure rather than reading prose.
        default_detail: The user-facing message used when the raiser supplies
            none. It describes the problem and what to do about it, and quotes
            no internal detail.
    """

    status_code: int = 500
    error_code: str = "internal_error"
    default_detail: str = "The service could not complete the request."

    def __init__(
        self, detail: str | None = None, headers: dict[str, str] | None = None
    ) -> None:
        """Record the message and any response headers for this error.

        Args:
            detail: User-facing message; ``default_detail`` when None.
            headers: Extra response headers to send with the error, if any.
        """
        self.detail: str = detail if detail is not None else self.default_detail
        self.headers = headers
        super().__init__(self.detail)


class DatabaseUnavailableError(AppError):
    """The database could not be reached or could not answer the query.

    Raised by routes in place of a hand-built 503, and produced from an
    escaping SQLAlchemy error by :func:`sqlalchemy_error_handler`. A caller
    cannot tell those two paths apart, which is the point: a database that is
    down is one failure, reported one way.
    """

    status_code: int = 503
    error_code: str = "database_unavailable"
    default_detail: str = (
        "Database unavailable: the service could not reach its database. "
        "Please try again shortly."
    )


def error_body(detail: str) -> dict[str, str]:
    """Build the one error body shape this service returns.

    Args:
        detail: The user-facing message.

    Returns:
        dict[str, str]: ``{"detail": detail}`` — the shape documented in
            ``docs/API.md`` and used by every error response here.
    """
    return {"detail": detail}


async def _respond(error: AppError) -> Response:
    """Answer an AppError with the documented error body.

    Args:
        error: The error a route raised, or one built from an escaping error.

    Returns:
        Response: A JSON response carrying ``{"detail": ...}`` and the
            error's status code and headers.
    """
    return JSONResponse(
        status_code=error.status_code,
        content=error_body(error.detail),
        headers=error.headers,
    )


async def app_error_handler(request: Request, exc: Exception) -> Response:
    """Turn an :class:`AppError` into the documented error response.

    Args:
        request: The request that failed, named in the log line only.
        exc: The raised error. A non-AppError reaching a registered handler is
            reported as an unrecognised failure, never as a stack trace.

    Returns:
        Response: The JSON error response for this request.
    """
    error = exc if isinstance(exc, AppError) else AppError()
    cause = error.__cause__ or error.__context__
    # The caller sees the fixed message; the log keeps what actually broke,
    # so a route that raises `from exc` loses nothing an operator would want.
    logger.warning(
        "%s %s failed with %s: %s%s",
        request.method,
        request.url.path,
        error.error_code,
        error.detail,
        f" (cause: {type(cause).__name__}: {cause})" if cause is not None else "",
    )
    return await _respond(error)


async def sqlalchemy_error_handler(request: Request, exc: Exception) -> Response:
    """Turn an escaping database error into a 503, with the cause logged.

    The safety net for a route that never wrapped its query: the driver's
    message goes to the log, the caller gets the same 503 body every other
    endpoint gives.

    Args:
        request: The request that failed, named in the log line only.
        exc: The SQLAlchemy error that escaped.

    Returns:
        Response: A 503 JSON error response.
    """
    logger.error(
        "%s %s lost the database: %s: %s",
        request.method,
        request.url.path,
        type(exc).__name__,
        exc,
    )
    return await _respond(DatabaseUnavailableError())


def register_error_handlers(app: FastAPI) -> None:
    """Register the application's error handlers on ``app``.

    Called once from ``src/main.py``. ``AppError`` covers its subclasses,
    including :class:`DatabaseUnavailableError`; ``SQLAlchemyError`` is the
    safety net for database errors no route caught.

    Args:
        app: The application to attach the handlers to.
    """
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(DatabaseUnavailableError, app_error_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)


__all__ = [
    "AppError",
    "DatabaseUnavailableError",
    "app_error_handler",
    "error_body",
    "register_error_handlers",
    "sqlalchemy_error_handler",
]
