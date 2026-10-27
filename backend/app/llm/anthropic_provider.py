"""Provider für Claude über das offizielle `anthropic`-SDK mit Tool Use."""

import json
from typing import Any

import anthropic

from app.leitplanken.daten import als_nutzereingabe, als_werkzeugergebnis
from app.llm.base import (
    AssistantMessage,
    LlmError,
    Message,
    ToolCall,
    ToolResult,
    ToolSpec,
    UserMessage,
)


def _parse_input(arguments: str) -> dict[str, Any]:
    try:
        geparst = json.loads(arguments)
    except json.JSONDecodeError:
        return {}
    return geparst if isinstance(geparst, dict) else {}


def to_anthropic_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """Werkzeugergebnisse gehören bei Anthropic in eine Nutzernachricht; aufeinanderfolgende
    Ergebnisse werden zu einer Nachricht zusammengefasst."""
    result: list[dict[str, Any]] = []
    for message in messages:
        match message:
            case UserMessage(text=text):
                result.append({"role": "user", "content": als_nutzereingabe(text)})
            case AssistantMessage(text=text, tool_calls=tool_calls):
                bloecke: list[dict[str, Any]] = []
                if text:
                    bloecke.append({"type": "text", "text": text})
                bloecke.extend(
                    {
                        "type": "tool_use",
                        "id": call.id,
                        "name": call.name,
                        "input": _parse_input(call.arguments),
                    }
                    for call in tool_calls
                )
                if bloecke:
                    result.append({"role": "assistant", "content": bloecke})
            case ToolResult(call_id=call_id, content=content, is_error=is_error):
                block = {
                    "type": "tool_result",
                    "tool_use_id": call_id,
                    "content": als_werkzeugergebnis(content),
                    "is_error": is_error,
                }
                vorige = result[-1] if result else None
                if (
                    vorige is not None
                    and vorige["role"] == "user"
                    and isinstance(vorige["content"], list)
                ):
                    vorige["content"].append(block)
                else:
                    result.append({"role": "user", "content": [block]})
    return result


def to_anthropic_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
    return [
        {"name": tool.name, "description": tool.description, "input_schema": tool.parameters}
        for tool in tools
    ]


class AnthropicProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int,
        timeout_seconds: float,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self._client = client or anthropic.Anthropic(
            api_key=api_key, timeout=timeout_seconds, max_retries=1
        )
        self._model = model
        self._max_tokens = max_tokens

    def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
        allow_tools: bool = True,
    ) -> AssistantMessage:
        optionen: dict[str, Any] = {}
        if tools:
            # Auch ohne erlaubte Aufrufe müssen die Werkzeuge mitgeschickt werden, sobald
            # der Verlauf tool_use-Blöcke enthält.
            optionen["tools"] = to_anthropic_tools(tools)
            optionen["tool_choice"] = {"type": "auto" if allow_tools else "none"}
        try:
            antwort = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                messages=to_anthropic_messages(messages),  # type: ignore[arg-type]
                **optionen,
            )
        except anthropic.AnthropicError as fehler:
            raise LlmError(type(fehler).__name__) from fehler
        texte: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in antwort.content:
            if block.type == "text":
                texte.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=json.dumps(block.input))
                )
        return AssistantMessage(text="".join(texte), tool_calls=tool_calls)

    def check_available(self) -> None:
        # Der Key wird beim Start geprüft; ein Probeaufruf würde Kosten verursachen.
        return None
