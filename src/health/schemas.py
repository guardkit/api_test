"""Health check response schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Health check response model."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"status": "ok", "version": "0.1.0"},
            ]
        }
    )

    status: str = Field(description="Service health status")
    version: str = Field(description="API version string")
