"""Konfiguration ausschließlich über Umgebungsvariablen."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings

LlmProvider = Literal["fake", "ollama", "anthropic"]

# Gleicher Standard wie in .env.example und im Build-Argument des Dockerfiles.
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://lotse:lotse@localhost:5432/lotse"
    llm_provider: LlmProvider = "fake"
    cors_origins: list[str] = ["http://localhost:5173"]
    data_dir: Path = Path("/data")
    embedding_model: str = DEFAULT_EMBEDDING_MODEL


@lru_cache
def get_settings() -> Settings:
    return Settings()
