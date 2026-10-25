"""CLI `python -m app.ingest`: Wissensdokumente idempotent in die Vektordatenbank laden."""

import sys
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_engine, run_migrations
from app.embeddings import Embedder, FastEmbedder
from app.wissen import (
    EMBEDDING_DIM,
    Abschnitt,
    KeineWissensdokumente,
    WissenAbschnitt,
    load_abschnitte,
)


@dataclass(frozen=True)
class Bestand:
    id: int
    dokument: str
    inhalt_hash: str


@dataclass
class IngestPlan:
    neu: list[tuple[Abschnitt, str]] = field(default_factory=list)
    unveraendert: list[tuple[int, Abschnitt]] = field(default_factory=list)
    geloescht: list[int] = field(default_factory=list)


def plan_ingest(bestand: list[Bestand], abschnitte: list[Abschnitt], model_name: str) -> IngestPlan:
    """Abgleich über `(dokument, inhalt_hash)`. Geänderte Abschnitte gelten als neu + gelöscht."""
    vorhanden: dict[tuple[str, str], list[int]] = defaultdict(list)
    for zeile in sorted(bestand, key=lambda b: b.id):
        vorhanden[(zeile.dokument, zeile.inhalt_hash)].append(zeile.id)

    plan = IngestPlan()
    for abschnitt in abschnitte:
        inhalt_hash = abschnitt.inhalt_hash(model_name)
        ids = vorhanden.get((abschnitt.dokument, inhalt_hash))
        if ids:
            plan.unveraendert.append((ids.pop(0), abschnitt))
        else:
            plan.neu.append((abschnitt, inhalt_hash))
    plan.geloescht = sorted(i for ids in vorhanden.values() for i in ids)
    return plan


def ingest(
    session: Session, embedder: Embedder, abschnitte: list[Abschnitt], model_name: str
) -> IngestPlan:
    bestand = [
        Bestand(id=z.id, dokument=z.dokument, inhalt_hash=z.inhalt_hash)
        for z in session.execute(
            select(WissenAbschnitt.id, WissenAbschnitt.dokument, WissenAbschnitt.inhalt_hash)
        )
    ]
    plan = plan_ingest(bestand, abschnitte, model_name)

    if plan.geloescht:
        session.execute(delete(WissenAbschnitt).where(WissenAbschnitt.id.in_(plan.geloescht)))
    for zeilen_id, abschnitt in plan.unveraendert:
        # Nicht eingebettete Felder können sich ohne neuen Hash ändern.
        zeile = session.get_one(WissenAbschnitt, zeilen_id)
        zeile.position = abschnitt.position
        zeile.fachrichtungen = abschnitt.fachrichtungen

    vektoren = embedder.embed_passages([a.einbettungstext for a, _ in plan.neu])
    for (abschnitt, inhalt_hash), vektor in zip(plan.neu, vektoren, strict=True):
        if len(vektor) != EMBEDDING_DIM:
            raise ValueError(
                f"Modell {model_name} liefert {len(vektor)} Dimensionen, "
                f"die Tabelle erwartet {EMBEDDING_DIM}."
            )
        session.add(
            WissenAbschnitt(
                dokument=abschnitt.dokument,
                titel=abschnitt.titel,
                abschnitt=abschnitt.abschnitt,
                position=abschnitt.position,
                text=abschnitt.text,
                fachrichtungen=abschnitt.fachrichtungen,
                inhalt_hash=inhalt_hash,
                embedding=vektor,
            )
        )
    return plan


def main() -> None:
    settings = get_settings()
    # Zuerst die Dokumente lesen: Fehlen sie, wird die Datenbank gar nicht angefasst.
    try:
        abschnitte = load_abschnitte(settings.data_dir)
    except KeineWissensdokumente as fehler:
        sys.exit(f"Ingest abgebrochen, nichts gelöscht: {fehler}")
    run_migrations()
    embedder = FastEmbedder(settings.embedding_model)
    with Session(get_engine()) as session, session.begin():
        plan = ingest(session, embedder, abschnitte, settings.embedding_model)
    print(
        f"Ingest: {len(plan.neu)} neu, {len(plan.unveraendert)} unverändert, "
        f"{len(plan.geloescht)} gelöscht"
    )


if __name__ == "__main__":
    main()
