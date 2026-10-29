"""Simuliertes Terminsystem: freie Termine aus den Öffnungszeiten, Anfragen in der Datenbank."""

import hashlib
import logging
import re
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import Date, DateTime, Engine, Text, Uuid, delete, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.standorte import Standort, StandortKatalog, normalize
from app.termine.base import (
    ZEITZONE,
    Anfrage,
    AnfrageAntwort,
    FachrichtungUngueltig,
    Slot,
    StandortUnbekannt,
    TerminNichtVerfuegbar,
    Terminsystem,
    TerminsystemNichtErreichbar,
)

logger = logging.getLogger(__name__)

TAGE = 14
RASTER = timedelta(minutes=30)
LOESCHFRIST = timedelta(days=30)
WOCHENTAGE = ("mo", "di", "mi", "do", "fr")

_INTERVALL = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})\s*$")

Intervall = tuple[time, time]


class Base(DeclarativeBase):
    pass


class TerminanfrageZeile(Base):
    __tablename__ = "terminanfragen"

    anfrage_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    slot_id: Mapped[str] = mapped_column(Text, unique=True)
    standort_id: Mapped[str] = mapped_column(Text)
    fachrichtung: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    geburtsdatum: Mapped[date] = mapped_column(Date)
    telefon: Mapped[str] = mapped_column(Text)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


def parse_oeffnungszeiten(text: str) -> list[Intervall]:
    """`08:00-12:00, 14:00-18:00` → zwei Intervalle, aufsteigend sortiert."""
    intervalle = []
    for teil in text.split(","):
        treffer = _INTERVALL.match(teil)
        if treffer is None:
            raise ValueError(f"Öffnungszeit nicht lesbar: {teil!r}")
        h1, m1, h2, m2 = (int(g) for g in treffer.groups())
        von, bis = time(h1, m1), time(h2, m2)
        if von >= bis:
            raise ValueError(f"Öffnungszeit endet vor dem Beginn: {teil!r}")
        intervalle.append((von, bis))
    return sorted(intervalle)


def slot_id(standort_id: str, fachrichtung: str, beginn: datetime) -> str:
    return f"{standort_id}|{fachrichtung}|{beginn.isoformat()}"


def ist_belegt(standort_id: str, fachrichtung: str, beginn: datetime) -> bool:
    """Etwa die Hälfte der Termine ist belegt, stabil zwischen Neustarts."""
    schluessel = f"{standort_id}{fachrichtung}{beginn.isoformat()}".encode()
    return hashlib.sha256(schluessel).digest()[0] >= 128


def resolve_fachrichtung(standort: Standort, fachrichtung: str) -> str:
    """Vergleich wie in Spec 002, aber es muss genau eine Fachrichtung passen.

    Ein exakter Treffer gewinnt, sonst wäre z. B. „Innere Medizin" neben
    „Innere Medizin – Kardiologie" mehrdeutig.
    """
    gesucht = normalize(fachrichtung.strip())
    exakt = [f for f in standort.fachrichtungen if gesucht == normalize(f)]
    treffer = exakt or [f for f in standort.fachrichtungen if gesucht and gesucht in normalize(f)]
    if len(treffer) != 1:
        raise FachrichtungUngueltig(
            f"Standort {standort.id} hat keine eindeutige Fachrichtung '{fachrichtung}'. "
            f"Verfügbar: {', '.join(standort.fachrichtungen)}"
        )
    return treffer[0]


def _jetzt() -> datetime:
    return datetime.now(ZEITZONE)


class SimuliertesTerminsystem(Terminsystem):
    def __init__(
        self,
        katalog: StandortKatalog,
        engine: Engine,
        jetzt: Callable[[], datetime] = _jetzt,
    ) -> None:
        self._katalog = katalog
        self._engine = engine
        self._jetzt = jetzt
        # Beim Start parsen: Unlesbare Öffnungszeiten fallen sofort auf, nicht erst bei Anfragen.
        self._zeiten = {
            s.id: [parse_oeffnungszeiten(getattr(s.oeffnungszeiten, tag)) for tag in WOCHENTAGE]
            for s in katalog.search()
        }

    def _beginne(self, standort: Standort, ab: date) -> Iterator[datetime]:
        """Alle Termin-Beginne der nächsten TAGE Tage ab `ab`, aufsteigend."""
        for versatz in range(TAGE):
            tag = ab + timedelta(days=versatz)
            if tag.weekday() >= len(WOCHENTAGE):
                continue
            for von, bis in self._zeiten[standort.id][tag.weekday()]:
                beginn = datetime.combine(tag, von, ZEITZONE)
                ende = datetime.combine(tag, bis, ZEITZONE)
                while beginn + RASTER <= ende:
                    yield beginn
                    beginn += RASTER

    def _slot(self, standort: Standort, fachrichtung: str, beginn: datetime) -> Slot:
        return Slot(
            slot_id=slot_id(standort.id, fachrichtung, beginn),
            standort_id=standort.id,
            standort_name=standort.name,
            fachrichtung=fachrichtung,
            beginn=beginn.isoformat(),
        )

    def freie_termine(
        self, standort_id: str, fachrichtung: str, ab_datum: date | None, limit: int
    ) -> list[Slot]:
        standort = self._katalog.get(standort_id)
        if standort is None:
            raise StandortUnbekannt(standort_id)
        fachrichtung = resolve_fachrichtung(standort, fachrichtung)
        jetzt = self._jetzt()
        try:
            with Session(self._engine) as session:
                angefragt = set(
                    session.scalars(
                        select(TerminanfrageZeile.slot_id).where(
                            TerminanfrageZeile.standort_id == standort.id,
                            TerminanfrageZeile.fachrichtung == fachrichtung,
                        )
                    )
                )
        except SQLAlchemyError as fehler:
            raise TerminsystemNichtErreichbar(type(fehler).__name__) from fehler
        slots: list[Slot] = []
        for beginn in self._beginne(standort, jetzt.date()):
            if len(slots) >= limit:
                break
            if beginn <= jetzt or (ab_datum is not None and beginn.date() < ab_datum):
                continue
            if ist_belegt(standort.id, fachrichtung, beginn):
                continue
            slot = self._slot(standort, fachrichtung, beginn)
            if slot.slot_id not in angefragt:
                slots.append(slot)
        return slots

    def _angebotener_slot(self, gesucht: str) -> Slot | None:
        """Der Slot zu `gesucht`, wenn er existiert, in der Zukunft liegt und nicht belegt ist."""
        teile = gesucht.split("|")
        if len(teile) != 3:
            return None
        standort_id, fachrichtung, beginn_text = teile
        standort = self._katalog.get(standort_id)
        if standort is None or fachrichtung not in standort.fachrichtungen:
            return None
        try:
            beginn = datetime.fromisoformat(beginn_text)
        except ValueError:
            return None
        if beginn.tzinfo is None:
            return None
        beginn = beginn.astimezone(ZEITZONE)
        jetzt = self._jetzt()
        if beginn <= jetzt or beginn not in self._beginne(standort, jetzt.date()):
            return None
        slot = self._slot(standort, fachrichtung, beginn)
        # Nur die kanonische Schreibweise (z. B. nicht „Z" statt „+01:00") ist eine Slot-ID.
        if slot.slot_id != gesucht or ist_belegt(standort.id, fachrichtung, beginn):
            return None
        return slot

    def anfrage_stellen(self, anfrage: Anfrage) -> AnfrageAntwort:
        slot = self._angebotener_slot(anfrage.slot_id)
        if slot is None:
            raise TerminNichtVerfuegbar(anfrage.slot_id)
        anfrage_id = uuid.uuid4()
        zeile = TerminanfrageZeile(
            anfrage_id=anfrage_id,
            slot_id=slot.slot_id,
            standort_id=slot.standort_id,
            fachrichtung=slot.fachrichtung,
            name=anfrage.name,
            geburtsdatum=anfrage.geburtsdatum,
            telefon=anfrage.telefon,
            erstellt_am=self._jetzt().astimezone(UTC),
        )
        with Session(self._engine) as session:
            session.add(zeile)
            try:
                session.commit()
            except IntegrityError:
                # Schon angefragt (UNIQUE slot_id). Die Ausnahme nicht loggen: Sie enthält
                # die Werte der Zeile, also auch Name und Telefon.
                raise TerminNichtVerfuegbar(anfrage.slot_id) from None
        return AnfrageAntwort(anfrage_id=str(anfrage_id), slot=slot)

    def anfrage_abrufen(self, anfrage_id: str) -> AnfrageAntwort | None:
        try:
            schluessel = uuid.UUID(anfrage_id)
        except ValueError:
            return None
        with Session(self._engine) as session:
            zeile = session.get(TerminanfrageZeile, schluessel)
            if zeile is None:
                return None
            standort = self._katalog.get(zeile.standort_id)
            slot = Slot(
                slot_id=zeile.slot_id,
                standort_id=zeile.standort_id,
                standort_name=standort.name if standort else zeile.standort_id,
                fachrichtung=zeile.fachrichtung,
                beginn=zeile.slot_id.rsplit("|", 1)[-1],
            )
            return AnfrageAntwort(anfrage_id=str(zeile.anfrage_id), slot=slot)

    def alte_anfragen_loeschen(self) -> int:
        grenze = self._jetzt().astimezone(UTC) - LOESCHFRIST
        with Session(self._engine) as session:
            ergebnis = session.execute(
                delete(TerminanfrageZeile).where(TerminanfrageZeile.erstellt_am < grenze)
            )
            session.commit()
        anzahl: int = getattr(ergebnis, "rowcount", 0)
        return anzahl
