"""Version endpoint response schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class VersionResponse(BaseModel):
    """Version information response model."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "version": "0.1.0",
                    "commit": "1b0f90b",
                    "service": "api",
                },
            ]
        }
    )

    version: str = Field(description="Application version string")
    commit: str = Field(description="Git commit hash (7 characters)")
    service: str = Field(description="Service name")
