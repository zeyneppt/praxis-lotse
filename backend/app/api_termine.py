"""HTTP-Endpunkte der Terminanfrage (Spec 005)."""

import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.ratenbegrenzung import Ratenbegrenzer, pruefe_rate
from app.termine import (
    Anfrage,
    AnfrageAntwort,
    FachrichtungUngueltig,
    Slot,
    StandortUnbekannt,
    TerminNichtVerfuegbar,
    Terminsystem,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/termine")

NICHT_VERFUEGBAR = "Termin nicht mehr verfügbar"


def get_terminsystem(request: Request) -> Terminsystem:
    terminsystem: Terminsystem = request.app.state.terminsystem
    return terminsystem


def get_termine_ratenbegrenzer(request: Request) -> Ratenbegrenzer:
    begrenzer: Ratenbegrenzer = request.app.state.termine_ratenbegrenzer
    return begrenzer


def anfrage_rate_pruefen(
    request: Request,
    begrenzer: Annotated[Ratenbegrenzer, Depends(get_termine_ratenbegrenzer)],
) -> None:
    pruefe_rate(request, begrenzer, "Terminanfrage")


TerminsystemDep = Annotated[Terminsystem, Depends(get_terminsystem)]


@router.get("/freie", response_model=list[Slot])
def freie_termine(
    terminsystem: TerminsystemDep,
    standort_id: Annotated[str, Query(max_length=100)],
    fachrichtung: Annotated[str, Query(max_length=100)],
    ab_datum: date | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[Slot]:
    try:
        return terminsystem.freie_termine(standort_id, fachrichtung, ab_datum, limit)
    except StandortUnbekannt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Standort nicht gefunden"
        ) from None
    except FachrichtungUngueltig as fehler:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(fehler)
        ) from None


@router.post(
    "/anfragen",
    response_model=AnfrageAntwort,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(anfrage_rate_pruefen)],
)
def anfrage_stellen(anfrage: Anfrage, terminsystem: TerminsystemDep) -> AnfrageAntwort:
    try:
        antwort = terminsystem.anfrage_stellen(anfrage)
    except TerminNichtVerfuegbar:
        # Ohne slot_id: Sie ist hier ungeprüfter Freitext des Clients (Log-Injection, ggf. Namen).
        logger.info("Terminanfrage abgelehnt: Termin nicht verfügbar")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=NICHT_VERFUEGBAR) from None
    # Nur Kennungen, nie Name, Geburtsdatum oder Telefon.
    logger.info(
        "Terminanfrage angelegt: anfrage_id=%s slot_id=%s", antwort.anfrage_id, antwort.slot.slot_id
    )
    return antwort


@router.get("/anfragen/{anfrage_id}", response_model=AnfrageAntwort)
def anfrage_abrufen(anfrage_id: str, terminsystem: TerminsystemDep) -> AnfrageAntwort:
    antwort = terminsystem.anfrage_abrufen(anfrage_id)
    if antwort is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anfrage nicht gefunden")
    return antwort
