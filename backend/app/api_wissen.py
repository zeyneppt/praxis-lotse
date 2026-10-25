"""HTTP-Endpunkte der Wissensbasis (Spec 003)."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from app.db import get_engine
from app.embeddings import Embedder
from app.wissen import DokumentInfo, Treffer, list_dokumente, search

router = APIRouter(prefix="/api/wissen")


def get_embedder(request: Request) -> Embedder:
    embedder: Embedder = request.app.state.embedder
    return embedder


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session


DbSession = Annotated[Session, Depends(get_session)]


class SucheAnfrage(BaseModel):
    # Nur Leerzeichen gilt als leere Frage (422), daher vor der Längenprüfung trimmen.
    frage: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    k: int = Field(default=3, ge=1, le=10)


class SucheAntwort(BaseModel):
    treffer: list[Treffer]


@router.post("/suche", response_model=SucheAntwort)
def wissen_suche(
    anfrage: SucheAnfrage,
    session: DbSession,
    embedder: Annotated[Embedder, Depends(get_embedder)],
) -> SucheAntwort:
    return SucheAntwort(treffer=search(session, embedder.embed_query(anfrage.frage), anfrage.k))


@router.get("/dokumente", response_model=list[DokumentInfo])
def wissen_dokumente(session: DbSession) -> list[DokumentInfo]:
    return list_dokumente(session)
