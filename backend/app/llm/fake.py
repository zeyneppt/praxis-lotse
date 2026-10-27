"""Deterministischer Provider ohne Netzwerk für Tests und CI."""

import json

from app.llm.base import AssistantMessage, Message, ToolCall, ToolResult, ToolSpec, UserMessage

WISSEN_WERKZEUG = "wissen_suchen"
NICHTS_GEFUNDEN = "[Testmodus] Nichts gefunden"


def _treffer(ergebnis: ToolResult) -> list[dict[str, str]]:
    if ergebnis.is_error:
        return []
    treffer: list[dict[str, str]] = json.loads(ergebnis.content).get("treffer") or []
    return treffer


class FakeProvider:
    """Ruft immer `wissen_suchen` mit der Nutzernachricht auf und nennt den besten Treffer.

    Die Quellen (Dokumente aller Treffer) gibt er wie ein echtes Modell in einer letzten
    Zeile `Quellen: …` an; der Server entfernt sie aus der Antwort.
    """

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
        if isinstance(letzte, ToolResult) and (treffer := _treffer(letzte)):
            dokumente = ", ".join(dict.fromkeys(t["dokument"] for t in treffer))
            return AssistantMessage(
                text=f"[Testmodus] Gefunden in: {treffer[0]['titel']}\nQuellen: {dokumente}"
            )
        return AssistantMessage(text=NICHTS_GEFUNDEN)

    def check_available(self) -> None:
        return None
