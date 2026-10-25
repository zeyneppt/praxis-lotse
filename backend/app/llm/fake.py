"""Deterministischer Provider ohne Netzwerk für Tests und CI."""

import json

from app.llm.base import AssistantMessage, Message, ToolCall, ToolResult, ToolSpec, UserMessage

WISSEN_WERKZEUG = "wissen_suchen"
NICHTS_GEFUNDEN = "[Testmodus] Nichts gefunden"


def _bester_titel(ergebnis: ToolResult) -> str | None:
    if ergebnis.is_error:
        return None
    treffer = json.loads(ergebnis.content).get("treffer") or []
    return str(treffer[0]["titel"]) if treffer else None


class FakeProvider:
    """Ruft immer `wissen_suchen` mit der Nutzernachricht auf und nennt den besten Treffer."""

    def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
        allow_tools: bool = True,
    ) -> AssistantMessage:
        letzte = messages[-1]
        if isinstance(letzte, UserMessage) and allow_tools:
            argumente = json.dumps({"frage": letzte.text}, ensure_ascii=False)
            return AssistantMessage(
                text="",
                tool_calls=[
                    ToolCall(id=f"fake-{len(messages)}", name=WISSEN_WERKZEUG, arguments=argumente)
                ],
            )
        if isinstance(letzte, ToolResult):
            titel = _bester_titel(letzte)
            if titel is not None:
                return AssistantMessage(text=f"[Testmodus] Gefunden in: {titel}")
        return AssistantMessage(text=NICHTS_GEFUNDEN)

    def check_available(self) -> None:
        return None
