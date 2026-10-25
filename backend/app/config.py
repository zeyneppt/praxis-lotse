"""Konfiguration ausschließlich über Umgebungsvariablen."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings

LlmProvider = Literal["fake", "ollama", "anthropic"]


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://lotse:lotse@localhost:5432/lotse"
    llm_provider: LlmProvider = "fake"
    cors_origins: list[str] = ["http://localhost:5173"]
    data_dir: Path = Path("/data")


@lru_cache
def get_settings() -> Settings:
    return Settings()
