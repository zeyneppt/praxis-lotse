"""Terminanfragen über eine austauschbare Termin-Schnittstelle (Spec 005)."""

from app.termine.base import (
    ZEITZONE,
    Anfrage,
    AnfrageAntwort,
    FachrichtungUngueltig,
    Slot,
    StandortUnbekannt,
    TerminNichtVerfuegbar,
    Terminsystem,
)
from app.termine.simuliert import SimuliertesTerminsystem

__all__ = [
    "ZEITZONE",
    "Anfrage",
    "AnfrageAntwort",
    "FachrichtungUngueltig",
    "SimuliertesTerminsystem",
    "Slot",
    "StandortUnbekannt",
    "TerminNichtVerfuegbar",
    "Terminsystem",
]
