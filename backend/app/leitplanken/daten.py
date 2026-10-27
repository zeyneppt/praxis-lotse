"""Kennzeichnung von Nutzereingaben und Werkzeugergebnissen als Daten (Prompt-Injection)."""

import re

# Verhindert, dass Text die Markierung vorzeitig schließt oder fälscht.
_MARKIERUNG = re.compile(r"<(/?)(nutzereingabe|werkzeugergebnis)", re.I)


def _entschaerfe(text: str) -> str:
    return _MARKIERUNG.sub(r"‹\1\2", text)


def als_nutzereingabe(text: str) -> str:
    return f"<nutzereingabe>\n{_entschaerfe(text)}\n</nutzereingabe>"


def als_werkzeugergebnis(text: str) -> str:
    return f"<werkzeugergebnis>\n{_entschaerfe(text)}\n</werkzeugergebnis>"
