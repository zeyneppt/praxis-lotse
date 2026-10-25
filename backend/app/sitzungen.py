"""Chatverläufe pro Sitzung, nur im Speicher (keine dauerhafte Speicherung)."""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from app.llm.base import AssistantMessage, Message, UserMessage

MAX_NACHRICHTEN = 20
ABLAUF_SEKUNDEN = 30 * 60


@dataclass
class _Sitzung:
    zuletzt: float
    nachrichten: list[Message] = field(default_factory=list)


class SitzungsSpeicher:
    """Hält pro Sitzung nur Nutzernachrichten und Antworttexte, keine Werkzeugaufrufe.

    So bleibt der Verlauf beim Kürzen gültig (kein Werkzeugergebnis ohne Aufruf) und
    beginnt immer mit einer Nutzernachricht.
    """

    def __init__(
        self,
        max_nachrichten: int = MAX_NACHRICHTEN,
        ablauf_sekunden: float = ABLAUF_SEKUNDEN,
        uhr: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_nachrichten
        self._ablauf = ablauf_sekunden
        self._uhr = uhr
        self._sitzungen: dict[str, _Sitzung] = {}
        self._lock = threading.Lock()

    def verlauf(self, sitzung_id: str) -> list[Message]:
        with self._lock:
            self._abgelaufene_entfernen()
            sitzung = self._sitzungen.get(sitzung_id)
            if sitzung is None:
                return []
            sitzung.zuletzt = self._uhr()
            return list(sitzung.nachrichten)

    def speichern(self, sitzung_id: str, nachricht: str, antwort: str) -> None:
        with self._lock:
            sitzung = self._sitzungen.setdefault(sitzung_id, _Sitzung(zuletzt=self._uhr()))
            sitzung.zuletzt = self._uhr()
            sitzung.nachrichten += [UserMessage(nachricht), AssistantMessage(antwort)]
            # Paarweise kürzen, damit der Verlauf mit einer Nutzernachricht beginnt.
            while len(sitzung.nachrichten) > self._max:
                del sitzung.nachrichten[:2]

    def __len__(self) -> int:
        with self._lock:
            self._abgelaufene_entfernen()
            return len(self._sitzungen)

    def _abgelaufene_entfernen(self) -> None:
        grenze = self._uhr() - self._ablauf
        for sitzung_id in [s for s, sitzung in self._sitzungen.items() if sitzung.zuletzt < grenze]:
            del self._sitzungen[sitzung_id]
