"""Regelbasierte Erkennung eines eindeutigen Terminwunschs. Läuft vor dem LLM (Spec 009).

Kleine Modelle rufen das Terminwerkzeug nicht zuverlässig auf und erfinden dann Termine.
Nennt eine Nachricht „Termin", genau eine Fachrichtung und einen Ort oder Standort,
antwortet deshalb der Server selbst – mit Terminen ausschließlich aus dem Terminsystem.
"""

import re
from dataclasses import dataclass
from typing import Literal

from app.standorte import Standort, StandortKatalog, normalize

_WORT = re.compile(r"\w+")


@dataclass(frozen=True)
class Terminwunsch:
    fachrichtung: str
    ort: str
    standort: Standort | None  # ausdrücklich genannter Standort; hat Vorrang vor dem Ort
    am_ort: list[Standort]  # Standorte am Ort (bzw. der genannte) mit der Fachrichtung, evtl. leer
    im_verbund: list[Standort]  # alle Standorte mit der Fachrichtung


def _woerter(text: str) -> list[str]:
    return _WORT.findall(normalize(text))


def _nennt_termin(woerter: list[str]) -> bool:
    # Auch in zusammengesetzten Wörtern („Untersuchungstermin", „Wunschtermin").
    return any("termin" in w for w in woerter)


def nennt_termin(nachricht: str) -> bool:
    """Enthält die Nachricht ein Wort mit `termin`?"""
    return _nennt_termin(_woerter(nachricht))


def nennt_angaben(nachricht: str, katalog: StandortKatalog) -> bool:
    """Nennt die Nachricht `termin`, eine Fachrichtung, einen Ort oder einen Standort?"""
    woerter = _woerter(nachricht)
    standorte = katalog.search()
    return (
        _nennt_termin(woerter)
        or any(_nennt_fachrichtung(woerter, f) for f in katalog.fachrichtungen())
        or any(_nennt_ort(woerter, s.ort) for s in standorte)
        or _genannter_standort(woerter, standorte) is not None
    )


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


def _enthaelt_folge(woerter: list[str], folge: list[str]) -> list[int]:
    """Startpositionen, an denen `folge` als Wortfolge in `woerter` steht."""
    n = len(folge)
    return [i for i in range(len(woerter) - n + 1) if woerter[i : i + n] == folge]


def _genannter_standort(
    woerter: list[str], standorte: list[Standort]
) -> Standort | None | Literal[False]:
    """Der genannte Standort, `None` ohne Nennung, `False` bei mehreren Standorten.

    Gilt der volle Name („MVZ Nürnberg Süd") oder der Name ohne „MVZ " („Nürnberg Süd").
    Ist der Kurzname nur ein Ort („MVZ Stein" → „Stein"), zählt er als Ort, nicht als
    Standort. Eine Nennung innerhalb einer längeren („MVZ Erlangen" in „MVZ Erlangen Süd")
    zählt nicht.
    """
    orte = {tuple(_woerter(s.ort)) for s in standorte}
    nennungen: list[tuple[int, int, Standort]] = []
    for s in standorte:
        voll = _woerter(s.name)
        formen = [voll]
        if voll[0] == "mvz" and len(voll) > 1 and tuple(voll[1:]) not in orte:
            formen.append(voll[1:])
        for form in formen:
            nennungen += [(i, i + len(form), s) for i in _enthaelt_folge(woerter, form)]
    genannt = {
        s.id: s
        for a, e, s in nennungen
        if not any(a2 <= a and e <= e2 and (a2, e2) != (a, e) for a2, e2, _ in nennungen)
    }
    if len(genannt) > 1:
        return False
    return next(iter(genannt.values()), None)


def erkenne_terminwunsch(nachricht: str, katalog: StandortKatalog) -> Terminwunsch | None:
    """Terminwunsch mit genau einer Fachrichtung und genau einem Ort oder Standort, sonst `None`."""
    woerter = _woerter(nachricht)
    if not _nennt_termin(woerter):
        return None
    fachrichtungen = [f for f in katalog.fachrichtungen() if _nennt_fachrichtung(woerter, f)]
    if len(fachrichtungen) != 1:
        return None
    (fachrichtung,) = fachrichtungen
    standorte = katalog.search()
    im_verbund = [s for s in standorte if fachrichtung in s.fachrichtungen]
    standort = _genannter_standort(woerter, standorte)
    if standort is False:
        return None
    if standort is not None:
        # Ergänzung (Mensch): Ein genannter Standort hat Vorrang vor dem Ort.
        return Terminwunsch(
            fachrichtung=fachrichtung,
            ort=standort.ort,
            standort=standort,
            am_ort=[standort] if fachrichtung in standort.fachrichtungen else [],
            im_verbund=im_verbund,
        )
    orte = sorted({s.ort for s in standorte if _nennt_ort(woerter, s.ort)})
    if len(orte) != 1:
        return None
    (ort,) = orte
    return Terminwunsch(
        fachrichtung=fachrichtung,
        ort=ort,
        standort=None,
        am_ort=[s for s in im_verbund if s.ort == ort],
        im_verbund=im_verbund,
    )


# --- Allgemeiner Terminwunsch (Spec 010) -------------------------------------
# Fehlt Fachrichtung oder Ort, erfinden kleine Modelle Angebote. Der Server fragt deshalb
# selbst nach – nur mit Angaben aus dem Standortverzeichnis.

_WUNSCH_PRAEFIXE = ("frei", "buch", "vereinbar")
# Diese Fragen beantwortet die Wissensbasis.
_AUSSCHLUSS_PRAEFIXE = ("absag", "verschieb", "stornier", "mitbring")


@dataclass(frozen=True)
class AllgemeinerTerminwunsch:
    """Höchstens eines ist gesetzt: Fachrichtung, Standort oder Ort; nichts → Rückfrage."""

    fachrichtung: str | None = None
    standort: Standort | None = None
    ort: str | None = None


def _drueckt_wunsch_aus(woerter: list[str]) -> bool:
    return any(w.startswith(_WUNSCH_PRAEFIXE) or w == "einen" for w in woerter)


def _schliesst_aus(woerter: list[str]) -> bool:
    return any(w.startswith(_AUSSCHLUSS_PRAEFIXE) for w in woerter)


def erkenne_allgemeinen_terminwunsch(
    nachricht: str, katalog: StandortKatalog
) -> AllgemeinerTerminwunsch | None:
    """Terminwunsch, dem Fachrichtung oder Ort fehlt; `None`, wenn Spec 009 greift."""
    woerter = _woerter(nachricht)
    if not (_nennt_termin(woerter) and _drueckt_wunsch_aus(woerter)) or _schliesst_aus(woerter):
        return None
    if erkenne_terminwunsch(nachricht, katalog) is not None:
        return None
    fachrichtungen = [f for f in katalog.fachrichtungen() if _nennt_fachrichtung(woerter, f)]
    standorte = katalog.search()
    standort = _genannter_standort(woerter, standorte)
    orte = sorted({s.ort for s in standorte if _nennt_ort(woerter, s.ort)})
    if len(fachrichtungen) == 1 and standort is None and not orte:
        return AllgemeinerTerminwunsch(fachrichtung=fachrichtungen[0])
    if fachrichtungen or standort is False:
        return AllgemeinerTerminwunsch()
    if standort is not None:
        return AllgemeinerTerminwunsch(standort=standort)
    if len(orte) == 1:
        return AllgemeinerTerminwunsch(ort=orte[0])
    return AllgemeinerTerminwunsch()
