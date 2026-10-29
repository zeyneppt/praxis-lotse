"""Schnittstelle zum Terminsystem (Spec 005).

Eine Anbindung an ein echtes Praxisverwaltungssystem ersetzt nur die Implementierung
von `Terminsystem`; API und Chat sprechen ausschließlich mit dieser Klasse.
"""

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import AfterValidator, BaseModel, StrictBool, StringConstraints

ZEITZONE = ZoneInfo("Europe/Berlin")


class Slot(BaseModel):
    slot_id: str
    standort_id: str
    standort_name: str
    fachrichtung: str
    beginn: str  # ISO 8601 mit Offset von Europe/Berlin, z. B. 2026-10-27T09:30:00+01:00


def heute() -> date:
    return datetime.now(ZEITZONE).date()


def _in_der_vergangenheit(wert: date) -> date:
    if wert >= heute():
        raise ValueError("Geburtsdatum muss in der Vergangenheit liegen")
    return wert


MIN_TELEFON_ZIFFERN = 6


def _genug_ziffern(wert: str) -> str:
    # Ergänzung (Mensch) zu Spec 005: Sonst wären z. B. sechs Leerzeichen gültig.
    if sum(zeichen.isdigit() for zeichen in wert) < MIN_TELEFON_ZIFFERN:
        raise ValueError(f"Telefonnummer muss mindestens {MIN_TELEFON_ZIFFERN} Ziffern enthalten")
    return wert


def _eingewilligt(wert: bool) -> bool:
    if not wert:
        raise ValueError("Einwilligung in die Datenverarbeitung ist erforderlich")
    return wert


class Anfrage(BaseModel):
    slot_id: Annotated[str, StringConstraints(max_length=200)]
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
    geburtsdatum: Annotated[date, AfterValidator(_in_der_vergangenheit)]
    telefon: Annotated[
        str, StringConstraints(pattern=r"^[0-9 +\-/]{6,30}$"), AfterValidator(_genug_ziffern)
    ]
    einwilligung_datenschutz: Annotated[StrictBool, AfterValidator(_eingewilligt)]


class AnfrageAntwort(BaseModel):
    """Bewusst ohne personenbezogene Felder."""

    anfrage_id: str
    status: Literal["angefragt"] = "angefragt"
    slot: Slot


class StandortUnbekannt(Exception):
    pass


class FachrichtungUngueltig(Exception):
    """Die Fachrichtung trifft keine oder mehrere Fachrichtungen des Standorts."""


class TerminsystemNichtErreichbar(Exception):
    """Das Terminsystem antwortet nicht (z. B. Datenbank oder Schnittstelle ausgefallen)."""


class TerminNichtVerfuegbar(Exception):
    """Slot belegt, schon angefragt, vergangen oder nicht existent."""


class Terminsystem(ABC):
    @abstractmethod
    def freie_termine(
        self, standort_id: str, fachrichtung: str, ab_datum: date | None, limit: int
    ) -> list[Slot]:
        """Freie Termine aufsteigend nach Beginn.

        Wirft `StandortUnbekannt` oder `FachrichtungUngueltig`.
        """

    @abstractmethod
    def anfrage_stellen(self, anfrage: Anfrage) -> AnfrageAntwort:
        """Wirft `TerminNichtVerfuegbar`."""

    @abstractmethod
    def anfrage_abrufen(self, anfrage_id: str) -> AnfrageAntwort | None: ...

    @abstractmethod
    def alte_anfragen_loeschen(self) -> int:
        """Löscht Anfragen, die älter als die Löschfrist sind; liefert ihre Anzahl."""
