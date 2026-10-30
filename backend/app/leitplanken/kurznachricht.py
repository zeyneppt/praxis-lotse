"""Kurze Nachrichten ohne Frageinhalt gehen nicht an das LLM (Spec 010, Ergänzung).

Ohne Verlaufsauswertung kann der Assistent „ja" oder „ok" nicht sinnvoll fortsetzen;
kleine Modelle raten dann. Notfall und Terminwunsch werden vorher geprüft. Nennt die
Nachricht `termin`, eine Fachrichtung, einen Ort oder einen Standort („Termin absagen",
„Öffnungszeiten Fürth?"), hat sie Frageinhalt und geht weiter an das LLM.
"""

import re
from typing import Literal

from app.leitplanken.terminwunsch import nennt_angaben
from app.standorte import StandortKatalog, normalize

MAX_WOERTER = 2
_WORT = re.compile(r"\w+")


def erkenne_kurznachricht(
    nachricht: str, katalog: StandortKatalog
) -> Literal["danke", "kurz"] | None:
    """`"danke"` für einen Dank, `"kurz"` für andere Nachrichten ohne Frageinhalt."""
    woerter = _WORT.findall(normalize(nachricht))
    if len(woerter) > MAX_WOERTER or nennt_angaben(nachricht, katalog):
        return None
    # „danke", „dankeschön", „vielen Dank"
    return "danke" if any(w.startswith("dank") for w in woerter) else "kurz"
