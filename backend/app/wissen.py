"""Wissensbasis: Dokumente in Abschnitte zerlegen, speichern und semantisch durchsuchen."""

import hashlib
import logging
import re
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from pgvector.sqlalchemy import Vector
from pydantic import BaseModel
from sqlalchemy import ARRAY, Integer, String, Text, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

logger = logging.getLogger(__name__)

WISSEN_VERZEICHNIS = "wissen"
EMBEDDING_DIM = 384
MAX_TREFFER_PRO_DOKUMENT = 2

_KOPF = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_UEBERSCHRIFT = re.compile(r"^## (.+?)\s*$", re.MULTILINE)


class Base(DeclarativeBase):
    pass


class WissenAbschnitt(Base):
    __tablename__ = "wissen_abschnitte"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dokument: Mapped[str] = mapped_column(Text)
    titel: Mapped[str] = mapped_column(Text)
    abschnitt: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    fachrichtungen: Mapped[list[str]] = mapped_column(ARRAY(Text))
    inhalt_hash: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))


class Dokumentkopf(BaseModel):
    titel: str
    fachrichtungen: list[str]
    stand: date


@dataclass(frozen=True)
class Abschnitt:
    dokument: str
    titel: str
    abschnitt: str
    position: int
    text: str
    fachrichtungen: list[str]

    @property
    def einbettungstext(self) -> str:
        return f"{self.titel} – {self.abschnitt}\n\n{self.text}"

    def inhalt_hash(self, model_name: str) -> str:
        # Der Modellname gehört dazu: Ein Modellwechsel bettet alles neu ein.
        daten = f"{model_name}\n{self.einbettungstext}".encode()
        return hashlib.sha256(daten).hexdigest()


def parse_dokument(dokument: str, inhalt: str) -> list[Abschnitt]:
    """Ein Abschnitt pro `##`-Überschrift; der Text davor (Hinweiskasten) entfällt."""
    inhalt = inhalt.replace("\r\n", "\n")
    kopf_treffer = _KOPF.match(inhalt)
    if kopf_treffer is None:
        raise ValueError(f"{dokument}: YAML-Kopf fehlt")
    kopf = Dokumentkopf.model_validate(yaml.safe_load(kopf_treffer.group(1)))
    rumpf = inhalt[kopf_treffer.end() :]

    ueberschriften = list(_UEBERSCHRIFT.finditer(rumpf))
    abschnitte = []
    for position, treffer in enumerate(ueberschriften):
        ende = ueberschriften[position + 1].start() if position + 1 < len(ueberschriften) else None
        abschnitte.append(
            Abschnitt(
                dokument=dokument,
                titel=kopf.titel,
                abschnitt=treffer.group(1),
                position=position,
                text=rumpf[treffer.end() : ende].strip(),
                fachrichtungen=kopf.fachrichtungen,
            )
        )
    return abschnitte


def load_abschnitte(data_dir: Path) -> list[Abschnitt]:
    verzeichnis = data_dir / WISSEN_VERZEICHNIS
    return [
        abschnitt
        for datei in sorted(verzeichnis.glob("*.md"))
        for abschnitt in parse_dokument(datei.name, datei.read_text(encoding="utf-8"))
    ]


class Treffer(BaseModel):
    dokument: str
    titel: str
    abschnitt: str
    text: str
    score: float


class DokumentInfo(BaseModel):
    dokument: str
    titel: str
    abschnitte: int


def score_from_distance(distance: float) -> float:
    return round(1 - distance, 3)


def search(session: Session, query_embedding: list[float], k: int) -> list[Treffer]:
    """Die k ähnlichsten Abschnitte, höchstens zwei pro Dokument.

    Die Fensterfunktion liest alle Abschnitte (kein Index-Scan). Bei einigen
    Dutzend Abschnitten ist das schneller als jeder Index und dafür exakt.
    """
    start = time.perf_counter()
    distance = WissenAbschnitt.embedding.cosine_distance(query_embedding)
    rang = func.row_number().over(partition_by=WissenAbschnitt.dokument, order_by=distance)
    kandidaten = select(
        WissenAbschnitt.dokument,
        WissenAbschnitt.titel,
        WissenAbschnitt.abschnitt,
        WissenAbschnitt.text,
        distance.label("distance"),
        rang.label("rang"),
    ).subquery()
    abfrage = (
        select(kandidaten)
        .where(kandidaten.c.rang <= MAX_TREFFER_PRO_DOKUMENT)
        .order_by(kandidaten.c.distance, kandidaten.c.dokument)
        .limit(k)
    )
    treffer = [
        Treffer(
            dokument=zeile.dokument,
            titel=zeile.titel,
            abschnitt=zeile.abschnitt,
            text=zeile.text,
            score=score_from_distance(zeile.distance),
        )
        for zeile in session.execute(abfrage)
    ]
    # Bewusst ohne Fragetext: Er kann personenbezogene Daten enthalten.
    logger.info(
        "Wissenssuche: %d Treffer in %.1f ms", len(treffer), (time.perf_counter() - start) * 1000
    )
    return treffer


def list_dokumente(session: Session) -> list[DokumentInfo]:
    abfrage = (
        select(
            WissenAbschnitt.dokument,
            func.min(WissenAbschnitt.titel).label("titel"),
            func.count().label("abschnitte"),
        )
        .group_by(WissenAbschnitt.dokument)
        .order_by(WissenAbschnitt.dokument)
    )
    return [
        DokumentInfo(dokument=z.dokument, titel=z.titel, abschnitte=z.abschnitte)
        for z in session.execute(abfrage)
    ]
