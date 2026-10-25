"""Werkzeuge, die das LLM im Chat aufrufen kann (Spec 004).

Kleine lokale Modelle rufen Werkzeuge nicht immer korrekt auf. Unbekannte Namen und
ungültige Argumente werden deshalb als Fehler-Ergebnis an das Modell zurückgegeben.
"""

import json
from typing import Annotated, Any

from pydantic import BaseModel, StringConstraints, ValidationError
from sqlalchemy.orm import Session

from app.embeddings import Embedder
from app.llm.base import ToolCall, ToolResult, ToolSpec
from app.standorte import STANDORTE_DATEI, StandortKatalog
from app.wissen import search

WISSEN_K = 4
STANDORTE_TITEL = "Standortverzeichnis"

Filter = Annotated[str | None, StringConstraints(max_length=100)]


class StandorteSuchenArgs(BaseModel):
    fachrichtung: Filter = None
    ort: Filter = None


class WissenSuchenArgs(BaseModel):
    frage: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


STANDORTE_SUCHEN = ToolSpec(
    name="standorte_suchen",
    description=(
        "Sucht Standorte des MVZ-Verbunds mit Adresse, Telefon, Fachrichtungen und "
        "Öffnungszeiten. Beide Filter sind optional; ohne Filter kommen alle Standorte."
    ),
    parameters={
        "type": "object",
        "properties": {
            "fachrichtung": {
                "type": "string",
                "description": "Fachrichtung, z. B. Gastroenterologie oder Kardiologie",
            },
            "ort": {"type": "string", "description": "Ort, z. B. Erlangen oder Nürnberg"},
        },
    },
)

WISSEN_SUCHEN = ToolSpec(
    name="wissen_suchen",
    description=(
        "Durchsucht die Patienteninformationen des Verbunds (Vorbereitung auf "
        "Untersuchungen, Termine, Rezepte, erster Besuch, Notfälle)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "frage": {"type": "string", "description": "Die Frage in eigenen Worten"},
        },
        "required": ["frage"],
    },
)


def _fehler(call: ToolCall, meldung: str) -> ToolResult:
    inhalt = json.dumps({"fehler": meldung}, ensure_ascii=False)
    return ToolResult(call_id=call.id, name=call.name, content=inhalt, is_error=True)


def _parse_arguments(arguments: str) -> dict[str, Any]:
    if not arguments.strip():
        return {}
    geparst = json.loads(arguments)
    if not isinstance(geparst, dict):
        raise ValueError("Argumente müssen ein JSON-Objekt sein")
    return geparst


class Werkzeugkasten:
    """Führt Werkzeugaufrufe einer Chat-Nachricht aus und merkt sich die gelieferten Dokumente."""

    def __init__(self, katalog: StandortKatalog, session: Session, embedder: Embedder) -> None:
        self._katalog = katalog
        self._session = session
        self._embedder = embedder
        self.gelieferte_dokumente: dict[str, str] = {}  # dokument → titel, in Reihenfolge

    @property
    def specs(self) -> list[ToolSpec]:
        return [STANDORTE_SUCHEN, WISSEN_SUCHEN]

    def execute(self, call: ToolCall) -> ToolResult:
        namen = [spec.name for spec in self.specs]
        if call.name not in namen:
            return _fehler(
                call, f"Unbekanntes Werkzeug '{call.name}'. Verfügbar: {', '.join(namen)}"
            )
        try:
            argumente = _parse_arguments(call.arguments)
            if call.name == STANDORTE_SUCHEN.name:
                inhalt = self._standorte_suchen(StandorteSuchenArgs.model_validate(argumente))
            else:
                inhalt = self._wissen_suchen(WissenSuchenArgs.model_validate(argumente))
        except (ValueError, ValidationError) as fehler:
            # ValidationError und JSONDecodeError sind beides ValueErrors; die Meldung
            # enthält keine Nutzerdaten, nur Feldnamen und Fehlertypen.
            return _fehler(call, f"Ungültige Argumente: {_kurzfassung(fehler)}")
        return ToolResult(
            call_id=call.id, name=call.name, content=json.dumps(inhalt, ensure_ascii=False)
        )

    def _standorte_suchen(self, args: StandorteSuchenArgs) -> dict[str, Any]:
        standorte = self._katalog.search(fachrichtung=args.fachrichtung, ort=args.ort)
        if standorte:
            self.gelieferte_dokumente.setdefault(STANDORTE_DATEI, STANDORTE_TITEL)
        return {
            "dokument": STANDORTE_DATEI,
            "standorte": [standort.model_dump() for standort in standorte],
        }

    def _wissen_suchen(self, args: WissenSuchenArgs) -> dict[str, Any]:
        treffer = search(self._session, self._embedder.embed_query(args.frage), WISSEN_K)
        for t in treffer:
            self.gelieferte_dokumente.setdefault(t.dokument, t.titel)
        return {
            "treffer": [
                {"dokument": t.dokument, "titel": t.titel, "abschnitt": t.abschnitt, "text": t.text}
                for t in treffer
            ]
        }


def _kurzfassung(fehler: Exception) -> str:
    if isinstance(fehler, ValidationError):
        return "; ".join(
            f"{'.'.join(str(teil) for teil in e['loc']) or 'argumente'}: {e['type']}"
            for e in fehler.errors()
        )
    if isinstance(fehler, json.JSONDecodeError):
        return "kein gültiges JSON"
    return str(fehler)
