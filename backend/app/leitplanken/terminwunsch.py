"""Regelbasierte Erkennung eines eindeutigen Terminwunschs. Läuft vor dem LLM (Spec 009).

Kleine Modelle rufen das Terminwerkzeug nicht zuverlässig auf und erfinden dann Termine.
Nennt eine Nachricht „Termin", genau eine Fachrichtung und einen Ort, antwortet deshalb
der Server selbst – mit Terminen ausschließlich aus dem Terminsystem.
"""

import re
from dataclasses import dataclass

from app.standorte import Standort, StandortKatalog, normalize

_WORT = re.compile(r"\w+")


@dataclass(frozen=True)
class Terminwunsch:
    fachrichtung: str
    ort: str
    am_ort: list[Standort]  # Standorte am Ort mit der Fachrichtung, evtl. leer
    im_verbund: list[Standort]  # alle Standorte mit der Fachrichtung


def _woerter(text: str) -> list[str]:
    return _WORT.findall(normalize(text))


def _nennt_termin(woerter: list[str]) -> bool:
    return any(w.startswith("termin") for w in woerter)


def nennt_termin(nachricht: str) -> bool:
    """Enthält die Nachricht ein Wort, das mit `termin` beginnt?"""
    return _nennt_termin(_woerter(nachricht))


def _nennt_fachrichtung(woerter: list[str], name: str) -> bool:
    teile = _woerter(name)
    if len(teile) > 1:
        # Mehrwortnamen als Wortfolge; jedes Wort darf gebeugt sein („Inneren Medizin").
        n = len(teile)
        return any(
            all(w.startswith(t) for w, t in zip(woerter[i : i + n], teile, strict=True))
            for i in range(len(woerter) - n + 1)
        )
    (stamm,) = teile
    if stamm.endswith("ie"):
        # „Neurologen", „Kardiologin": Präfix ohne -ie schließt die volle Form mit ein.
        stamm = stamm[:-2]
    return any(w.startswith(stamm) for w in woerter)


def _nennt_ort(woerter: list[str], ort: str) -> bool:
    # Bei mehrteiligen Orten genügt das erste Wort („Lauf" → Lauf an der Pegnitz).
    return _woerter(ort)[0] in woerter


def erkenne_terminwunsch(nachricht: str, katalog: StandortKatalog) -> Terminwunsch | None:
    """Terminwunsch mit genau einer Fachrichtung und genau einem Ort, sonst `None`."""
    woerter = _woerter(nachricht)
    if not _nennt_termin(woerter):
        return None
    fachrichtungen = [f for f in katalog.fachrichtungen() if _nennt_fachrichtung(woerter, f)]
    if len(fachrichtungen) != 1:
        return None
    standorte = katalog.search()
    orte = sorted({s.ort for s in standorte if _nennt_ort(woerter, s.ort)})
    if len(orte) != 1:
        return None
    (fachrichtung,), (ort,) = fachrichtungen, orte
    im_verbund = [s for s in standorte if fachrichtung in s.fachrichtungen]
    return Terminwunsch(
        fachrichtung=fachrichtung,
        ort=ort,
        am_ort=[s for s in im_verbund if s.ort == ort],
        im_verbund=im_verbund,
    )
