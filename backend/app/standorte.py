"""Standorte des MVZ-Verbunds: Laden aus `standorte.json` und Suche im Speicher."""

import json
import unicodedata
from pathlib import Path

from pydantic import BaseModel, ConfigDict

STANDORTE_DATEI = "standorte.json"

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


class Oeffnungszeiten(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mo: str
    di: str
    mi: str
    do: str
    fr: str


class Standort(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    ort: str
    stadtteil: str | None
    adresse: str
    plz: str
    telefon: str
    fachrichtungen: list[str]
    oeffnungszeiten: Oeffnungszeiten
    barrierefrei: bool


def normalize(text: str) -> str:
    """Vergleichsform: ohne Groß-/Kleinschreibung, Umlaute umschrieben.

    `Gynäkologie` → `gynaekologie`. Zerlegte Umlaute (NFD, z. B. von macOS) werden
    vorher zusammengesetzt, sonst greift die Umschreibung nicht.
    """
    return unicodedata.normalize("NFC", text).casefold().translate(_UMLAUTE)


def _filter_term(value: str | None) -> str | None:
    """Normalisierter Filterwert; leer oder nur Leerzeichen bedeutet „kein Filter"."""
    stripped = value.strip() if value else ""
    return normalize(stripped) if stripped else None


class StandortKatalog:
    def __init__(self, standorte: list[Standort]) -> None:
        self._standorte = sorted(standorte, key=lambda s: s.id)
        self._nach_id = {s.id: s for s in self._standorte}

    def search(self, fachrichtung: str | None = None, ort: str | None = None) -> list[Standort]:
        fachrichtung_norm = _filter_term(fachrichtung)
        ort_norm = _filter_term(ort)
        return [
            s
            for s in self._standorte
            if (
                fachrichtung_norm is None
                or any(fachrichtung_norm in normalize(f) for f in s.fachrichtungen)
            )
            and (ort_norm is None or ort_norm in normalize(s.ort))
        ]

    def get(self, standort_id: str) -> Standort | None:
        return self._nach_id.get(standort_id)

    def fachrichtungen(self) -> list[str]:
        eindeutig = {f for s in self._standorte for f in s.fachrichtungen}
        return sorted(eindeutig, key=lambda f: (normalize(f), f))


def load_katalog(data_dir: Path) -> StandortKatalog:
    inhalt = json.loads((data_dir / STANDORTE_DATEI).read_text(encoding="utf-8"))
    return StandortKatalog([Standort.model_validate(s) for s in inhalt["standorte"]])
