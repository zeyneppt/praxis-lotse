"""Ratenbegrenzung des Chats: gleitendes Fenster pro IP-Adresse (Spec 006)."""

import logging
import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)

MAX_NACHRICHTEN_PRO_MINUTE = 60
MAX_TERMINANFRAGEN_PRO_MINUTE = 20
FENSTER_SEKUNDEN = 60.0
# Schutz vor beliebig vielen IP-Adressen: ab dieser Größe werden abgelaufene Einträge entfernt.
AUFRAEUM_AB = 10_000
LIMIT_MELDUNG = "Zu viele Anfragen. Bitte warten Sie einen Moment."


class Ratenbegrenzer:
    def __init__(
        self,
        limit: int = MAX_NACHRICHTEN_PRO_MINUTE,
        fenster_sekunden: float = FENSTER_SEKUNDEN,
        uhr: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._fenster = fenster_sekunden
        self._uhr = uhr
        self._zeitpunkte: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def erlauben(self, schluessel: str) -> bool:
        """Zählt den Aufruf und sagt, ob er erlaubt ist. Abgelehnte Aufrufe zählen nicht mit."""
        jetzt = self._uhr()
        with self._lock:
            if len(self._zeitpunkte) >= AUFRAEUM_AB:
                self._aufraeumen(jetzt)
            zeiten = self._zeitpunkte.setdefault(schluessel, deque())
            while zeiten and zeiten[0] <= jetzt - self._fenster:
                zeiten.popleft()
            if len(zeiten) >= self._limit:
                return False
            zeiten.append(jetzt)
            return True

    def _aufraeumen(self, jetzt: float) -> None:
        grenze = jetzt - self._fenster
        for schluessel in [s for s, z in self._zeitpunkte.items() if not z or z[-1] <= grenze]:
            del self._zeitpunkte[schluessel]


def pruefe_rate(request: Request, begrenzer: Ratenbegrenzer, bereich: str) -> None:
    """Wirft 429, wenn die IP-Adresse des Aufrufers ihr Limit für `bereich` ausgeschöpft hat."""
    ip = request.client.host if request.client else "unbekannt"
    if not begrenzer.erlauben(ip):
        logger.warning("%s: Ratenbegrenzung ausgelöst", bereich)
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail=LIMIT_MELDUNG)
