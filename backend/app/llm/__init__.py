"""LLM-Provider: Auswahl über `LLM_PROVIDER`."""

import logging

from app.config import Settings
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import LlmError, LlmProvider
from app.llm.fake import FakeProvider
from app.llm.openai_compat import OpenAICompatProvider

logger = logging.getLogger(__name__)

# Ollama prüft keinen Key, das SDK verlangt aber einen.
OLLAMA_API_KEY = "ollama"


class LlmConfigError(Exception):
    """Die Konfiguration reicht nicht, um den gewählten Provider zu starten."""


def create_provider(settings: Settings) -> LlmProvider:
    match settings.llm_provider:
        case "fake":
            return FakeProvider()
        case "ollama":
            return OpenAICompatProvider(
                base_url=settings.ollama_base_url,
                api_key=OLLAMA_API_KEY,
                model=settings.llm_model,
                max_tokens=settings.llm_max_tokens,
                timeout_seconds=settings.llm_timeout_seconds,
            )
        case "anthropic":
            secret = settings.anthropic_api_key
            key = secret.get_secret_value().strip() if secret else ""
            if not key:
                raise LlmConfigError(
                    "LLM_PROVIDER=anthropic, aber ANTHROPIC_API_KEY ist nicht gesetzt."
                )
            return AnthropicProvider(
                api_key=key,
                model=settings.llm_model,
                max_tokens=settings.llm_max_tokens,
                timeout_seconds=settings.llm_timeout_seconds,
            )


def check_provider(provider: LlmProvider, settings: Settings) -> None:
    """Nur eine Warnung: Das Backend startet auch ohne erreichbares Modell."""
    try:
        provider.check_available()
    except LlmError as fehler:
        logger.warning(
            "LLM-Provider %s unter %s nicht erreichbar (%s). Chat-Anfragen liefern "
            'kategorie "fehler", bis der Dienst läuft.',
            settings.llm_provider,
            settings.ollama_base_url,
            fehler,
        )
