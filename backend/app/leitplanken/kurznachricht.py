"""Kurze Nachrichten ohne Frageinhalt gehen nicht an das LLM (Spec 010, Ergänzung).

Ohne Verlaufsauswertung kann der Assistent „ja" oder „ok" nicht sinnvoll fortsetzen;
kleine Modelle raten dann. Notfall und Terminwunsch werden vorher geprüft.
"""

import re
from typing import Literal

from app.standorte import normalize

MAX_WOERTER = 2
_WORT = re.compile(r"\w+")


def erkenne_kurznachricht(nachricht: str) -> Literal["danke", "kurz"] | None:
    """`"danke"` für einen Dank, `"kurz"` für andere Nachrichten mit höchstens 2 Wörtern."""
    woerter = _WORT.findall(normalize(nachricht))
    if len(woerter) > MAX_WOERTER:
        return None
    # „danke", „dankeschön", „vielen Dank"
    return "danke" if any(w.startswith("dank") for w in woerter) else "kurz"
