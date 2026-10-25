"""Provider für OpenAI-kompatible Schnittstellen: Ollama lokal, später auch Azure OpenAI.

Für Azure genügen eine andere `base_url` (`https://<ressource>.openai.azure.com/openai/v1/`),
ein API-Key und der Deployment-Name als Modell.
"""

import json
import uuid
from typing import Any

import openai

from app.llm.base import (
    AssistantMessage,
    LlmError,
    Message,
    ToolCall,
    ToolResult,
    ToolSpec,
    UserMessage,
)

AVAILABILITY_TIMEOUT_SECONDS = 3.0

# Qwen-Modelle schreiben Werkzeugaufrufe als `<tool_call>{"name": …, "arguments": …}</tool_call>`.
# Steht davor Text oder kommt das Tag verstümmelt an, erkennt Ollama den Aufruf nicht und
# liefert ihn als Antworttext aus. Deshalb zählt jedes JSON-Objekt dieser Form im Text.
_DECODER = json.JSONDecoder()


def _neue_id() -> str:
    return f"call_{uuid.uuid4().hex}"


def parse_text_tool_calls(text: str, namen: set[str]) -> list[ToolCall]:
    """Nur Objekte mit dem Namen eines angebotenen Werkzeugs zählen als Aufruf."""
    calls = []
    position = text.find("{")
    while position != -1:
        try:
            daten, ende = _DECODER.raw_decode(text, position)
        except json.JSONDecodeError:
            position = text.find("{", position + 1)
            continue
        if isinstance(daten, dict) and daten.get("name") in namen and "arguments" in daten:
            argumente = daten["arguments"]
            if not isinstance(argumente, str):
                argumente = json.dumps(argumente, ensure_ascii=False)
            calls.append(ToolCall(id=_neue_id(), name=daten["name"], arguments=argumente))
        position = text.find("{", ende)
    return calls


def to_openai_messages(system: str, messages: list[Message]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for message in messages:
        match message:
            case UserMessage(text=text):
                result.append({"role": "user", "content": text})
            case AssistantMessage(text=text, tool_calls=tool_calls):
                eintrag: dict[str, Any] = {"role": "assistant", "content": text or None}
                if tool_calls:
                    eintrag["tool_calls"] = [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {"name": call.name, "arguments": call.arguments},
                        }
                        for call in tool_calls
                    ]
                result.append(eintrag)
            case ToolResult(call_id=call_id, content=content):
                result.append({"role": "tool", "tool_call_id": call_id, "content": content})
    return result


def to_openai_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in tools
    ]


class OpenAICompatProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        max_tokens: int,
        timeout_seconds: float,
        client: openai.OpenAI | None = None,
    ) -> None:
        # Wiederholungen übernimmt das SDK nicht: Ein langsames lokales Modell würde
        # sonst ein Vielfaches des Zeitlimits blockieren.
        self._client = client or openai.OpenAI(
            base_url=base_url, api_key=api_key, timeout=timeout_seconds, max_retries=0
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
            optionen["tools"] = to_openai_tools(tools)
            optionen["tool_choice"] = "auto" if allow_tools else "none"
        try:
            antwort = self._client.chat.completions.create(
                model=self._model,
                messages=to_openai_messages(system, messages),  # type: ignore[arg-type]
                max_tokens=self._max_tokens,
                **optionen,
            )
        except openai.OpenAIError as fehler:
            raise LlmError(type(fehler).__name__) from fehler
        if not antwort.choices:
            raise LlmError("Antwort ohne Inhalt")
        nachricht = antwort.choices[0].message
        tool_calls = [
            # Manche lokalen Server liefern keine ID; die Zuordnung braucht aber eine.
            ToolCall(
                id=call.id or _neue_id(),
                name=call.function.name,
                arguments=call.function.arguments or "",
            )
            for call in nachricht.tool_calls or []
            if call.type == "function"
        ]
        text = nachricht.content or ""
        if allow_tools and not tool_calls:
            if text_calls := parse_text_tool_calls(text, {tool.name for tool in tools}):
                return AssistantMessage(text="", tool_calls=text_calls)
        return AssistantMessage(text=text, tool_calls=tool_calls)

    def check_available(self) -> None:
        try:
            self._client.with_options(timeout=AVAILABILITY_TIMEOUT_SECONDS).models.list()
        except openai.OpenAIError as fehler:
            raise LlmError(type(fehler).__name__) from fehler
