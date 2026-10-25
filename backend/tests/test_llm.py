import json
import logging
from collections.abc import Callable
from typing import Any

import anthropic
import httpx2
import openai
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.llm import LlmConfigError, check_provider, create_provider
from app.llm.anthropic_provider import AnthropicProvider, to_anthropic_messages
from app.llm.base import AssistantMessage, LlmError, Message, ToolCall, ToolResult, UserMessage
from app.llm.fake import FakeProvider
from app.llm.openai_compat import (
    OpenAICompatProvider,
    parse_text_tool_calls,
    to_openai_messages,
)
from app.werkzeuge import STANDORTE_SUCHEN

Handler = Callable[[httpx2.Request], httpx2.Response]
NAMEN = {"standorte_suchen", "wissen_suchen"}

VERLAUF: list[Message] = [
    UserMessage("Wo in Erlangen?"),
    AssistantMessage("", [ToolCall("c1", "standorte_suchen", '{"ort": "Erlangen"}')]),
    ToolResult("c1", "standorte_suchen", '{"standorte": []}'),
    AssistantMessage("Moment.", [ToolCall("c2", "wissen_suchen", "{kaputt")]),
    ToolResult("c2", "wissen_suchen", '{"fehler": "x"}', is_error=True),
]


# --- Auswahl -----------------------------------------------------------------


def test_create_provider_fake() -> None:
    assert isinstance(create_provider(Settings(llm_provider="fake")), FakeProvider)


def test_create_provider_ollama() -> None:
    assert isinstance(create_provider(Settings(llm_provider="ollama")), OpenAICompatProvider)


@pytest.mark.parametrize("key", [None, "", "   "])
def test_anthropic_ohne_key_startet_nicht(key: str | None) -> None:
    settings = Settings(
        llm_provider="anthropic", anthropic_api_key=SecretStr(key) if key is not None else None
    )
    with pytest.raises(LlmConfigError, match="ANTHROPIC_API_KEY"):
        create_provider(settings)


def test_create_provider_anthropic() -> None:
    settings = Settings(llm_provider="anthropic", anthropic_api_key=SecretStr("sk-test"))
    assert isinstance(create_provider(settings), AnthropicProvider)


def test_nicht_erreichbares_ollama_ist_nur_eine_warnung(caplog: pytest.LogCaptureFixture) -> None:
    provider = openai_provider(lambda request: httpx2.Response(503))
    with caplog.at_level(logging.WARNING):
        check_provider(provider, Settings(llm_provider="ollama"))
    assert "nicht erreichbar" in caplog.text


# --- OpenAI-kompatibel (Ollama) ----------------------------------------------


def openai_provider(handler: Handler) -> OpenAICompatProvider:
    client = openai.OpenAI(
        api_key="ollama",
        base_url="http://ollama.test/v1",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    return OpenAICompatProvider("unbenutzt", "unbenutzt", "qwen2.5:7b", 800, 5.0, client=client)


def openai_antwort(message: dict[str, Any]) -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "id": "x",
            "object": "chat.completion",
            "created": 0,
            "model": "qwen2.5:7b",
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
        },
    )


def test_to_openai_messages() -> None:
    nachrichten = to_openai_messages("SYS", VERLAUF)

    assert nachrichten[0] == {"role": "system", "content": "SYS"}
    assert nachrichten[2] == {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "standorte_suchen", "arguments": '{"ort": "Erlangen"}'},
            }
        ],
    }
    assert nachrichten[3] == {"role": "tool", "tool_call_id": "c1", "content": '{"standorte": []}'}
    assert nachrichten[4]["content"] == "Moment."


def test_openai_provider_werkzeugaufruf() -> None:
    anfragen: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        anfragen.append(json.loads(request.content))
        return openai_antwort(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "",
                        "type": "function",
                        "function": {"name": "standorte_suchen", "arguments": '{"ort":"Erlangen"}'},
                    }
                ],
            }
        )

    antwort = openai_provider(handler).complete("SYS", [UserMessage("Hi")], [STANDORTE_SUCHEN])

    assert antwort.text == ""
    assert antwort.tool_calls[0].name == "standorte_suchen"
    assert antwort.tool_calls[0].arguments == '{"ort":"Erlangen"}'
    assert antwort.tool_calls[0].id.startswith("call_")  # leere ID ersetzt
    gesendet = anfragen[0]
    assert gesendet["model"] == "qwen2.5:7b"
    assert gesendet["max_tokens"] == 800
    assert gesendet["tool_choice"] == "auto"
    assert gesendet["tools"][0]["function"]["name"] == "standorte_suchen"


def test_openai_provider_ohne_werkzeuge() -> None:
    anfragen: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        anfragen.append(json.loads(request.content))
        return openai_antwort({"role": "assistant", "content": "Hallo!"})

    provider = openai_provider(handler)
    assert provider.complete("SYS", [UserMessage("Hi")], [STANDORTE_SUCHEN], False).text == "Hallo!"
    assert anfragen[0]["tool_choice"] == "none"


def test_openai_provider_erkennt_werkzeugaufruf_im_text() -> None:
    inhalt = (
        'Ich schaue nach.\n<tool_call>\n{"name": "standorte_suchen", '
        '"arguments": {"fachrichtung": "Akupunktur"}}\n</tool_call>'
    )
    provider = openai_provider(lambda r: openai_antwort({"role": "assistant", "content": inhalt}))

    antwort = provider.complete("SYS", [UserMessage("Hi")], [STANDORTE_SUCHEN])

    assert antwort.text == ""
    assert [(c.name, json.loads(c.arguments)) for c in antwort.tool_calls] == [
        ("standorte_suchen", {"fachrichtung": "Akupunktur"})
    ]


def test_werkzeugaufruf_im_text_zaehlt_nicht_ohne_erlaubte_werkzeuge() -> None:
    inhalt = '{"name": "standorte_suchen", "arguments": {}}'
    provider = openai_provider(lambda r: openai_antwort({"role": "assistant", "content": inhalt}))

    antwort = provider.complete("SYS", [UserMessage("Hi")], [STANDORTE_SUCHEN], False)

    assert antwort.tool_calls == []
    assert antwort.text == inhalt


@pytest.mark.parametrize(
    "text",
    [
        "Normale Antwort ohne Aufruf.",
        "<tool_call>{kaputt}</tool_call>",
        '<tool_call>{"arguments": {}}</tool_call>',
        '<tool_call>["liste"]</tool_call>',
        'Ein Objekt {"name": "Erlangen"} ohne Argumente ist kein Aufruf.',
        'Beispiel: {"name": "loesche_alles", "arguments": {}} (kein angebotenes Werkzeug)',
    ],
)
def test_parse_text_tool_calls_ignoriert_unbrauchbares(text: str) -> None:
    assert parse_text_tool_calls(text, NAMEN) == []


def test_parse_text_tool_calls_mit_verstuemmeltem_tag() -> None:
    # So von qwen2.5:7b über Ollama beobachtet: das öffnende Tag als Fantasiewort.
    text = 'onaut\n{"name": "standorte_suchen", "arguments": {"ort": "Schwabach"}}\n</tool_call>'
    calls = parse_text_tool_calls(text, NAMEN)
    assert [(c.name, json.loads(c.arguments)) for c in calls] == [
        ("standorte_suchen", {"ort": "Schwabach"})
    ]


def test_parse_text_tool_calls_mehrere_und_kaputte_dazwischen() -> None:
    text = (
        '{"name": "wissen_suchen", "arguments": {}} {kaputt '
        '{"name": "standorte_suchen", "arguments": {"x": {"y": 1}}}'
    )
    assert [(c.name, c.arguments) for c in parse_text_tool_calls(text, NAMEN)] == [
        ("wissen_suchen", "{}"),
        ("standorte_suchen", '{"x": {"y": 1}}'),
    ]


def test_parse_text_tool_calls_mit_argumenten_als_text() -> None:
    calls = parse_text_tool_calls(
        '<tool_call>{"name": "wissen_suchen", "arguments": "{}"}</tool_call>', NAMEN
    )
    assert [(c.name, c.arguments) for c in calls] == [("wissen_suchen", "{}")]


@pytest.mark.parametrize("status", [429, 500, 503])
def test_openai_provider_http_fehler_wird_llm_error(status: int) -> None:
    provider = openai_provider(lambda request: httpx2.Response(status, json={"error": "x"}))
    with pytest.raises(LlmError):
        provider.complete("SYS", [UserMessage("Hi")], [])


def test_openai_provider_timeout_wird_llm_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("zu langsam", request=request)

    with pytest.raises(LlmError, match="APITimeoutError"):
        openai_provider(handler).complete("SYS", [UserMessage("Hi")], [])


# --- Anthropic ---------------------------------------------------------------


def anthropic_provider(handler: Handler) -> AnthropicProvider:
    client = anthropic.Anthropic(
        api_key="sk-test",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    return AnthropicProvider("unbenutzt", "claude-haiku-5-5", 800, 5.0, client=client)


def test_to_anthropic_messages() -> None:
    zwei_ergebnisse: list[Message] = [
        UserMessage("Hi"),
        AssistantMessage("", [ToolCall("a", "x", "{}"), ToolCall("b", "y", "[1]")]),
        ToolResult("a", "x", "eins"),
        ToolResult("b", "y", "zwei", is_error=True),
    ]

    nachrichten = to_anthropic_messages(zwei_ergebnisse)

    assert len(nachrichten) == 3
    assert nachrichten[1]["content"][1] == {"type": "tool_use", "id": "b", "name": "y", "input": {}}
    assert nachrichten[2] == {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "a", "content": "eins", "is_error": False},
            {"type": "tool_result", "tool_use_id": "b", "content": "zwei", "is_error": True},
        ],
    }


def test_anthropic_provider_text_und_werkzeug() -> None:
    anfragen: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        anfragen.append(json.loads(request.content))
        return httpx2.Response(
            200,
            json={
                "id": "msg",
                "type": "message",
                "role": "assistant",
                "model": "claude-haiku-5-5",
                "stop_reason": "tool_use",
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
                "content": [
                    {"type": "text", "text": "Ich suche."},
                    {
                        "type": "tool_use",
                        "id": "tu1",
                        "name": "standorte_suchen",
                        "input": {"ort": "Erlangen"},
                    },
                ],
            },
        )

    antwort = anthropic_provider(handler).complete("SYS", VERLAUF, [STANDORTE_SUCHEN], False)

    assert antwort.text == "Ich suche."
    assert antwort.tool_calls == [ToolCall("tu1", "standorte_suchen", '{"ort": "Erlangen"}')]
    gesendet = anfragen[0]
    assert gesendet["system"] == "SYS"
    assert gesendet["max_tokens"] == 800
    assert gesendet["tool_choice"] == {"type": "none"}
    assert gesendet["tools"][0]["input_schema"] == STANDORTE_SUCHEN.parameters


def test_anthropic_provider_rate_limit_wird_llm_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        fehler = {"type": "rate_limit_error", "message": "langsam"}
        return httpx2.Response(429, json={"type": "error", "error": fehler})

    with pytest.raises(LlmError, match="RateLimitError"):
        anthropic_provider(handler).complete("SYS", [UserMessage("Hi")], [])
