"""Regelbasierte Notfallerkennung. Läuft vor jedem LLM-Aufruf (Spec 006).

Lieber einmal zu oft als einmal zu wenig auslösen: Die Muster sind bewusst weit gefasst.
"""

import re
from typing import Literal

NotfallArt = Literal["koerperlich", "seelisch"]

_UMSCHREIBUNG = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _normalisiere(text: str) -> str:
    """Kleinschreibung, Umlaute als ae/oe/ue/ss: „ohnmächtig" und „ohnmaechtig" sind gleich."""
    return text.casefold().translate(_UMSCHREIBUNG)


# Alle Muster sind für den normalisierten Text geschrieben. `W` überbrückt bis zu drei Wörter.
_W = r"\W+(?:\w+\W+){0,3}"

_KOERPERLICH = [
    r"brust\W{0,2}schmerz",
    r"schmerz\w*\W+(?:\w+\W+){0,2}brust",
    r"druck\w*\W+(?:\w+\W+){0,2}brust",
    r"herzinfarkt|herzstillstand",
    r"atemnot|luftnot|atembeschwerde|atemprobleme",
    r"nicht\s+(?:mehr\s+)?atmen",
    r"keine\s+luft|schlecht\w*\s+luft|ringt?\s+nach\s+luft",
    r"kaum\s+(?:noch\s+)?luft|kaum\s+(?:noch\s+)?atmen|schnapp\w*\s+nach\s+luft",
    r"bewusstlos|bewusstseinsverlust|nicht\s+(?:mehr\s+)?ansprechbar",
    r"ohnmaecht|ohnmacht|kollabiert",
    r"schlaganfall|hirnschlag",
    r"laehmung|gelaehmt",
    r"nicht\s+mehr\s+bewegen",
    r"sprachstoer",
    rf"spr\w+{_W}undeutlich|undeutlich\w*{_W}spr\w+|\blallt\b",
    rf"\bstark\w*{_W}blut(?:ung\w*|et|en)\b|\bblut(?:et|en)\b{_W}stark",
    r"(?:hoert|hoeren)\s+nicht\s+auf\s+zu\s+bluten|blutung\w*\s+(?:nicht\s+)?(?:stoppen|stillen)",
    r"krampfanfall|krampfanfaelle|epileptische\w*\s+anfall",
]

_SEELISCH = [
    r"suizid|selbstmord",
    r"(?:das|mein)\s+leben\s+(?:\w+\s+)?(?:nehm|genomm)\w*|(?:nehm|nimm|genomm)\w*\s+(?:\w+\s+)?das\s+leben",
    rf"\bmich\b{_W}umbring\w*|umbring\w*{_W}\bmich\b|\bbring\w*{_W}\bmich\b\W+(?:\w+\W+){{0,2}}um\b",
    r"nicht\s+mehr\s+(?:weiter\s*)?leben|nicht\s+mehr\s+am\s+leben",
    r"lebensmued",
]

_KOERPERLICH_RE = re.compile("|".join(f"(?:{m})" for m in _KOERPERLICH))
_SEELISCH_RE = re.compile("|".join(f"(?:{m})" for m in _SEELISCH))


def erkenne_notfall(text: str) -> NotfallArt | None:
    """Art des Notfalls oder `None`. Seelische Krisen haben Vorrang, ihre Antwort nennt auch 112."""
    normal = _normalisiere(text)
    if _SEELISCH_RE.search(normal):
        return "seelisch"
    if _KOERPERLICH_RE.search(normal):
        return "koerperlich"
    return None
