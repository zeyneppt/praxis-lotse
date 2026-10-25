"""Anbieterneutrale Nachrichten und die Schnittstelle, die jeder LLM-Provider erfüllt."""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema der Argumente


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    # Rohtext, wie ihn das Modell geliefert hat: kann ungültiges JSON sein.
    arguments: str


@dataclass(frozen=True)
class UserMessage:
    text: str


@dataclass(frozen=True)
class AssistantMessage:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    name: str
    content: str
    is_error: bool = False


Message = UserMessage | AssistantMessage | ToolResult


class LlmError(Exception):
    """Der Anbieter ist nicht erreichbar oder hat mit einem Fehler geantwortet."""


class LlmProvider(Protocol):
    def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
        allow_tools: bool = True,
    ) -> AssistantMessage:
        """Nächste Antwort des Modells. `allow_tools=False` verlangt eine Textantwort."""
        ...

    def check_available(self) -> None:
        """Wirft `LlmError`, wenn der Anbieter nicht erreichbar ist."""
        ...
