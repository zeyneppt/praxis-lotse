"""Kurze Nachrichten ohne Frageinhalt gehen nicht an das LLM (Spec 010, Ergänzung).

Ohne Verlaufsauswertung kann der Assistent „ja" oder „ok" nicht sinnvoll fortsetzen;
kleine Modelle raten dann. Notfall und Terminwunsch werden vorher geprüft. Als
Kurznachricht gilt nur, was ausschließlich aus Bestätigungs-, Gruß-, Dank- oder
Hilfewörtern besteht (Entscheidung Mensch nach Review); kurze Fragen wie
„Öffnungszeiten?" gehen weiter an die Wissensbasis.
"""

import re
from typing import Literal

from app.standorte import normalize

MAX_WOERTER = 2
_WORT = re.compile(r"\w+")
# Normalisiert (Kleinschreibung, Umlaute als ae/oe/ue/ss).
_FUELLWOERTER = frozenset(
    {
        # Bestätigung und Ablehnung
        "ja", "jo", "jep", "jawohl", "nein", "nee", "ok", "okay", "gut", "genau",
        "super", "prima", "klar", "passt", "bitte", "gerne", "gern",
        # Gruß
        "hallo", "hi", "hey", "moin", "servus", "tschuess", "ciao",
        # Dank
        "danke", "dankeschoen", "vielen", "dank",
        # Hilferuf ohne Inhalt; die Antwort nennt 112 und 116117
        "hilfe",
    }
)  # fmt: skip


def erkenne_kurznachricht(nachricht: str) -> Literal["danke", "kurz"] | None:
    """`"danke"` für einen Dank, `"kurz"` für andere Kurznachrichten ohne Frageinhalt."""
    woerter = _WORT.findall(normalize(nachricht))
    if not 0 < len(woerter) <= MAX_WOERTER or not all(w in _FUELLWOERTER for w in woerter):
        return None
    # „danke", „dankeschön", „vielen Dank"
    return "danke" if any(w.startswith("dank") for w in woerter) else "kurz"
