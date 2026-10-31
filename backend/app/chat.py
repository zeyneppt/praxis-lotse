"""Chat-Schleife: Das Modell ruft Werkzeuge auf und antwortet auf Grundlage der Ergebnisse."""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.leitplanken import texte
from app.leitplanken.kurznachricht import erkenne_kurznachricht
from app.leitplanken.notfall import erkenne_notfall
from app.leitplanken.terminwunsch import (
    AllgemeinerTerminwunsch,
    Terminwunsch,
    erkenne_allgemeinen_terminwunsch,
    erkenne_terminwunsch,
    nennt_termin,
)
from app.llm.base import (
    AssistantMessage,
    LlmProvider,
    Message,
    ToolCall,
    ToolResult,
    UserMessage,
)
from app.standorte import STANDORTE_DATEI, Standort
from app.termine import Slot
from app.werkzeuge import STANDORTE_TITEL, WISSEN_SUCHEN, Werkzeugkasten

logger = logging.getLogger(__name__)

MAX_WERKZEUGAUFRUFE = 4
SYSTEM_PROMPT_DATEI = Path(__file__).resolve().parent / "prompts" / "system.md"

KI_HINWEIS = "Sie sprechen mit einem KI-Assistenten. Er ersetzt keine ärztliche Beratung."
FEHLER_ANTWORT = (
    "Entschuldigung, der Assistent ist gerade nicht erreichbar. Bitte versuchen Sie es "
    "später noch einmal oder rufen Sie direkt bei Ihrem Standort an."
)
TERMINSYSTEM_FEHLER_ANTWORT = (
    "Entschuldigung, das Terminsystem ist gerade nicht erreichbar. Bitte versuchen Sie es "
    "später noch einmal oder rufen Sie direkt bei Ihrem Standort an."
)
LEERE_ANTWORT = (
    "Dazu kann ich Ihnen leider keine Auskunft geben. Bitte rufen Sie direkt bei Ihrem Standort an."
)
LIMIT_MELDUNG = "Werkzeuglimit erreicht. Antworte jetzt mit den vorhandenen Ergebnissen."

# Letzte Zeile „Quellen: …", auch mit Markdown-Fettdruck oder als „Quelle:".
_QUELLEN_ZEILE = re.compile(r"^[ \t>*_-]*quellen?[*_]*[ \t]*:(?P<inhalt>[^\n]*)$", re.I | re.M)
_EINTRAG_RAND = " \t*_`'\"()[]<>."
# Uhrzeit in einer Modellantwort, z. B. „09:00", „9.30" oder „9 Uhr" (Spec 009).
_UHRZEIT = re.compile(r"\b\d{1,2}[:.]\d{2}\b|\b\d{1,2} uhr\b", re.I)
# Markdown, das die Oberfläche nicht darstellt (Spec 010, Ergänzung). Listen mit „- " bleiben.
_FETT = re.compile(r"\*\*([^\n]+?)\*\*|(?<!\w)__([^\n]+?)__(?!\.?\w)")
_LINK = re.compile(r"\[([^\]\n]+)\]\((?:[^()\s]|\([^()\s]*\))*\)")
_UEBERSCHRIFT = re.compile(r"^[ \t]*#{1,6}[ \t]+", re.M)

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
    # Termine aus dem Terminsystem für die `aktion`; nie vom Modell formuliert.
    termin_vorschlag: list[Slot] | None = None


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

    Quelle ist nur, was das Modell bekommen hat **und** in der Zeile nennt (Dateiname oder
    Titel, Einträge durch Komma getrennt), jedes Dokument nur einmal. Fehlt die Zeile oder
    passt kein Eintrag, gibt es keine Quellen: Lieber keine als eine falsche Quellenangabe.
    """
    zeilen = list(_QUELLEN_ZEILE.finditer(antwort))
    if not zeilen:
        return antwort.strip(), []
    letzte = zeilen[-1]
    text = (antwort[: letzte.start()] + antwort[letzte.end() :]).strip()
    eintraege = {
        e.strip(_EINTRAG_RAND).casefold() for e in re.split(r"[,;]", letzte.group("inhalt"))
    }
    quellen = [
        Quelle(dokument=d, titel=t)
        for d, t in gelieferte.items()
        if d.casefold() in eintraege or t.casefold() in eintraege
    ]
    return text, quellen


def strip_markdown(text: str) -> str:
    """Entfernt Fettdruck, Links (der Text bleibt) und Überschriften-`#`."""
    text = _FETT.sub(lambda m: m.group(1) or m.group(2), text)
    text = _LINK.sub(r"\1", text)
    return _UEBERSCHRIFT.sub("", text)


def _liste(namen: list[str]) -> str:
    return namen[0] if len(namen) == 1 else f"{', '.join(namen[:-1])} und {namen[-1]}"


def _aufzaehlung(standorte: list[Standort]) -> str:
    return _liste([s.name for s in standorte])


def _terminwunsch_beantworten(wunsch: Terminwunsch, werkzeuge: Werkzeugkasten) -> ChatErgebnis:
    """Antwort ohne LLM; Termine kommen ausschließlich aus dem Terminsystem."""
    quellen = [Quelle(STANDORTE_DATEI, STANDORTE_TITEL)]
    if not wunsch.am_ort and wunsch.standort is not None:
        text = texte.TERMINWUNSCH_NICHT_AM_STANDORT.format(
            standort=wunsch.standort.name,
            fachrichtung=wunsch.fachrichtung,
            standorte=_aufzaehlung(wunsch.im_verbund),
        )
        return ChatErgebnis(text, "normal", quellen, 0)
    if not wunsch.am_ort:
        text = texte.TERMINWUNSCH_NICHT_AM_ORT.format(
            ort=wunsch.ort,
            fachrichtung=wunsch.fachrichtung,
            standorte=_aufzaehlung(wunsch.im_verbund),
        )
        return ChatErgebnis(text, "normal", quellen, 0)
    if len(wunsch.am_ort) > 1:
        text = texte.TERMINWUNSCH_MEHRERE.format(
            fachrichtung=wunsch.fachrichtung,
            ort=wunsch.ort,
            standorte=_aufzaehlung(wunsch.am_ort),
            beispiel=wunsch.am_ort[0].name,
        )
        return ChatErgebnis(text, "normal", quellen, 0)
    (standort,) = wunsch.am_ort
    slots = werkzeuge.termine_vorschlagen(standort.id, wunsch.fachrichtung)
    if not slots:
        text = texte.TERMINWUNSCH_KEINE_TERMINE.format(
            standort=standort.name, fachrichtung=wunsch.fachrichtung, telefon=standort.telefon
        )
        return ChatErgebnis(text, "normal", quellen, 0)
    text = texte.TERMINWUNSCH_TERMINE.format(
        fachrichtung=wunsch.fachrichtung, standort=standort.name
    )
    return ChatErgebnis(text, "normal", quellen, 0, termin_vorschlag=slots)


def _allgemeinen_terminwunsch_beantworten(
    wunsch: AllgemeinerTerminwunsch, werkzeuge: Werkzeugkasten
) -> ChatErgebnis:
    """Rückfrage ohne LLM; nennt nur, was das Standortverzeichnis hergibt (Spec 010)."""
    quellen = [Quelle(STANDORTE_DATEI, STANDORTE_TITEL)]
    katalog = werkzeuge.katalog
    if wunsch.fachrichtung is not None:
        fachrichtung = wunsch.fachrichtung
        im_verbund = [s for s in katalog.search() if fachrichtung in s.fachrichtungen]
        if len(im_verbund) == 1:
            # Nur ein Anbieter im Verbund: Termine wie bei einem vollständigen Wunsch.
            (standort,) = im_verbund
            return _terminwunsch_beantworten(
                Terminwunsch(
                    fachrichtung=fachrichtung,
                    ort=standort.ort,
                    standort=None,
                    am_ort=im_verbund,
                    im_verbund=im_verbund,
                ),
                werkzeuge,
            )
        text = texte.TERMINWUNSCH_STANDORTE_FUER_FACHRICHTUNG.format(
            fachrichtung=fachrichtung,
            standorte=_aufzaehlung(im_verbund),
            beispiel=im_verbund[0].name,
        )
    elif wunsch.standort is not None:
        fachrichtungen = sorted(wunsch.standort.fachrichtungen)
        text = texte.TERMINWUNSCH_FACHRICHTUNGEN_AM_STANDORT.format(
            standort=wunsch.standort.name,
            fachrichtungen=_liste(fachrichtungen),
            beispiel=fachrichtungen[0],
        )
    elif wunsch.ort is not None:
        am_ort = [s for s in katalog.search() if s.ort == wunsch.ort]
        fachrichtungen = sorted({f for s in am_ort for f in s.fachrichtungen})
        text = texte.TERMINWUNSCH_FACHRICHTUNGEN_AM_ORT.format(
            ort=wunsch.ort, fachrichtungen=_liste(fachrichtungen), beispiel=fachrichtungen[0]
        )
    else:
        text = texte.TERMINWUNSCH_RUECKFRAGE.format(fachrichtungen=_liste(katalog.fachrichtungen()))
    return ChatErgebnis(text, "normal", quellen, 0)


def run_chat(
    provider: LlmProvider,
    system_prompt: str,
    verlauf: list[Message],
    nachricht: str,
    werkzeuge: Werkzeugkasten,
) -> ChatErgebnis:
    """Wirft `LlmError` oder `TerminsystemNichtErreichbar`, wenn ein Dienst ausfällt."""
    # Regelbasiert und vor jedem LLM-Aufruf (Spec 006).
    if (notfall := erkenne_notfall(nachricht)) is not None:
        logger.info("Chat: Notfall erkannt (%s), LLM nicht aufgerufen", notfall)
        text = texte.NOTFALL_KOERPERLICH if notfall == "koerperlich" else texte.NOTFALL_SEELISCH
        return ChatErgebnis(
            text, "notfall", [Quelle(texte.NOTFALL_DOKUMENT, texte.NOTFALL_TITEL)], 0
        )
    # Ebenfalls regelbasiert, damit das Modell keine Termine erfinden kann (Spec 009).
    if (wunsch := erkenne_terminwunsch(nachricht, werkzeuge.katalog)) is not None:
        logger.info("Chat: Terminwunsch erkannt, LLM nicht aufgerufen")
        return _terminwunsch_beantworten(wunsch, werkzeuge)
    # Fehlen Fachrichtung oder Ort, fragt der Server selbst nach (Spec 010).
    if (allgemein := erkenne_allgemeinen_terminwunsch(nachricht, werkzeuge.katalog)) is not None:
        logger.info("Chat: allgemeiner Terminwunsch erkannt, LLM nicht aufgerufen")
        return _allgemeinen_terminwunsch_beantworten(allgemein, werkzeuge)
    # „ja", „ok" usw. kann der Assistent ohne Verlauf nicht fortsetzen (Spec 010, Ergänzung).
    if (kurz := erkenne_kurznachricht(nachricht)) is not None:
        logger.info("Chat: Kurznachricht erkannt, LLM nicht aufgerufen")
        text = texte.KURZNACHRICHT_DANKE if kurz == "danke" else texte.KURZNACHRICHT
        return ChatErgebnis(text, "normal", [], 0)
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

    # Ohne freie Termine gibt es nichts auszuwählen, also auch keine `aktion`.
    vorschlag = werkzeuge.termin_vorschlag or None
    if texte.KANARIE.casefold() in antwort.text.casefold():
        # Kein Inhalt im Log: Die Antwort kann den Systemprompt enthalten.
        logger.warning("Leitplanke: Antwort mit interner Kennung ersetzt")
        return ChatErgebnis(texte.STANDARDANTWORT, "normal", [], aufrufe, vorschlag)

    if nennt_termin(nachricht) and vorschlag is None and _UHRZEIT.search(antwort.text):
        # Uhrzeiten ohne Termine aus dem Terminsystem sind vermutlich erfunden.
        logger.warning("Leitplanke: Antwort mit Uhrzeit ohne Terminsystem ersetzt")
        return ChatErgebnis(texte.TERMIN_NUR_AUS_TERMINSYSTEM, "normal", [], aufrufe)

    text, quellen = extract_quellen(antwort.text, werkzeuge.gelieferte_dokumente)
    text = strip_markdown(text).strip()
    if not text:
        return ChatErgebnis(LEERE_ANTWORT, "normal", [], aufrufe, vorschlag)
    return ChatErgebnis(text, "normal", quellen, aufrufe, vorschlag)
