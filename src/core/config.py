"""Core configuration module for the FastAPI application."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment and .env file."""

    model_config = SettingsConfigDict(env_file=".env")

    app_name: str = "api"
    app_env: str = "development"
    debug: bool = False


settings = Settings()
