"""HTTP-Endpunkte der Standortsuche (Spec 002)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.standorte import Standort, StandortKatalog

router = APIRouter(prefix="/api")


def get_katalog(request: Request) -> StandortKatalog:
    katalog: StandortKatalog = request.app.state.standort_katalog
    return katalog


Katalog = Annotated[StandortKatalog, Depends(get_katalog)]


@router.get("/standorte", response_model=list[Standort])
def list_standorte(
    katalog: Katalog, fachrichtung: str | None = None, ort: str | None = None
) -> list[Standort]:
    return katalog.search(fachrichtung=fachrichtung, ort=ort)


@router.get("/standorte/{standort_id}", response_model=Standort)
def get_standort(standort_id: str, katalog: Katalog) -> Standort:
    standort = katalog.get(standort_id)
    if standort is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Standort nicht gefunden")
    return standort


@router.get("/fachrichtungen", response_model=list[str])
def list_fachrichtungen(katalog: Katalog) -> list[str]:
    return katalog.fachrichtungen()
