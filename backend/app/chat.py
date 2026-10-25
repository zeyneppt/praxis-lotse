"""Chat-Schleife: Das Modell ruft Werkzeuge auf und antwortet auf Grundlage der Ergebnisse."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.llm.base import (
    AssistantMessage,
    LlmProvider,
    Message,
    ToolCall,
    ToolResult,
    UserMessage,
)
from app.werkzeuge import WISSEN_SUCHEN, Werkzeugkasten

MAX_WERKZEUGAUFRUFE = 4
SYSTEM_PROMPT_DATEI = Path(__file__).resolve().parent / "prompts" / "system.md"

KI_HINWEIS = "Sie sprechen mit einem KI-Assistenten. Er ersetzt keine ärztliche Beratung."
FEHLER_ANTWORT = (
    "Entschuldigung, der Assistent ist gerade nicht erreichbar. Bitte versuchen Sie es "
    "später noch einmal oder rufen Sie direkt bei Ihrem Standort an."
)
LEERE_ANTWORT = (
    "Dazu kann ich Ihnen leider keine Auskunft geben. Bitte rufen Sie direkt bei Ihrem Standort an."
)
LIMIT_MELDUNG = "Werkzeuglimit erreicht. Antworte jetzt mit den vorhandenen Ergebnissen."

# Letzte Zeile „Quellen: …", auch mit Markdown-Fettdruck oder als „Quelle:".
_QUELLEN_ZEILE = re.compile(r"^[ \t>*_-]*quellen?[*_]*[ \t]*:(?P<inhalt>[^\n]*)$", re.I | re.M)
_KEINE = re.compile(r"^\W*(keine?|-|–|none)?\W*$", re.I)

Kategorie = Literal["normal", "notfall", "fehler"]


@dataclass(frozen=True)
class Quelle:
    dokument: str
    titel: str


@dataclass(frozen=True)
class ChatErgebnis:
    antwort: str
    kategorie: Kategorie
    quellen: list[Quelle]
    werkzeugaufrufe: int


def load_system_prompt(datei: Path = SYSTEM_PROMPT_DATEI) -> str:
    return datei.read_text(encoding="utf-8")


def _rueckfall_suche(nachricht: str) -> AssistantMessage:
    """Werkzeugaufruf, den der Server anstelle des Modells stellt."""
    argumente = json.dumps({"frage": nachricht}, ensure_ascii=False)
    return AssistantMessage("", [ToolCall("rueckfall-1", WISSEN_SUCHEN.name, argumente)])


def _limit_ergebnis(call: ToolCall) -> ToolResult:
    inhalt = json.dumps({"fehler": LIMIT_MELDUNG}, ensure_ascii=False)
    return ToolResult(call_id=call.id, name=call.name, content=inhalt, is_error=True)


def extract_quellen(antwort: str, gelieferte: dict[str, str]) -> tuple[str, list[Quelle]]:
    """Trennt die Quellenzeile von der Antwort und ordnet sie gelieferten Dokumenten zu.

    Nur Dokumente, die das Modell tatsächlich bekommen hat, können Quelle sein; jedes
    nur einmal. „Quellen: keine" ergibt keine Quellen. Fehlt die Zeile oder passt sie zu
    keinem Dokument, zählen alle gelieferten Dokumente (das Modell hat sie bekommen,
    aber die Angabe vergessen oder verunstaltet).
    """
    zeilen = list(_QUELLEN_ZEILE.finditer(antwort))
    alle = [Quelle(dokument=d, titel=t) for d, t in gelieferte.items()]
    if not zeilen:
        return antwort.strip(), alle
    letzte = zeilen[-1]
    text = (antwort[: letzte.start()] + antwort[letzte.end() :]).strip()
    inhalt = letzte.group("inhalt").casefold()
    if _KEINE.match(inhalt):
        return text, []
    genannt = [q for q in alle if q.dokument.casefold() in inhalt or q.titel.casefold() in inhalt]
    return text, genannt or alle


def run_chat(
    provider: LlmProvider,
    system_prompt: str,
    verlauf: list[Message],
    nachricht: str,
    werkzeuge: Werkzeugkasten,
) -> ChatErgebnis:
    """Wirft `LlmError`, wenn der Anbieter scheitert."""
    nachrichten: list[Message] = [*verlauf, UserMessage(nachricht)]
    aufrufe = 0
    while True:
        werkzeuge_erlaubt = aufrufe < MAX_WERKZEUGAUFRUFE
        antwort = provider.complete(
            system_prompt, nachrichten, werkzeuge.specs, allow_tools=werkzeuge_erlaubt
        )
        if aufrufe == 0 and not antwort.tool_calls:
            # Kleine Modelle antworten oft aus eigenem Wissen, statt nachzuschlagen. Eine
            # Antwort ohne Werkzeugergebnis verwirft der Server und sucht selbst in der
            # Wissensbasis; das Modell antwortet dann auf Grundlage der Treffer.
            antwort = _rueckfall_suche(nachricht)
        # Ohne erlaubte Werkzeuge zählen nur noch Texte, auch wenn das Modell sich nicht daran hält.
        elif not werkzeuge_erlaubt or not antwort.tool_calls:
            break
        nachrichten.append(antwort)
        for call in antwort.tool_calls:
            if aufrufe < MAX_WERKZEUGAUFRUFE:
                nachrichten.append(werkzeuge.execute(call))
                aufrufe += 1
            else:
                # Jeder Aufruf braucht ein Ergebnis, sonst lehnt der Anbieter den Verlauf ab.
                nachrichten.append(_limit_ergebnis(call))

    text, quellen = extract_quellen(antwort.text, werkzeuge.gelieferte_dokumente)
    if not text:
        return ChatErgebnis(LEERE_ANTWORT, "normal", [], aufrufe)
    return ChatErgebnis(text, "normal", quellen, aufrufe)
