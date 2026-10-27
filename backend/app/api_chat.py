"""HTTP-Endpunkt des Chat-Assistenten (Spec 004)."""

import logging
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, StringConstraints

from app.api_standorte import Katalog
from app.api_termine import TerminsystemDep
from app.api_wissen import DbSession, get_embedder
from app.chat import FEHLER_ANTWORT, KI_HINWEIS, Kategorie, run_chat
from app.embeddings import Embedder
from app.llm.base import LlmError, LlmProvider
from app.logging import redact
from app.ratenbegrenzung import Ratenbegrenzer, pruefe_rate
from app.sitzungen import SitzungsSpeicher
from app.termine import Slot
from app.werkzeuge import Werkzeugkasten

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def get_provider(request: Request) -> LlmProvider:
    provider: LlmProvider = request.app.state.llm_provider
    return provider


def get_system_prompt(request: Request) -> str:
    prompt: str = request.app.state.system_prompt
    return prompt


def get_sitzungen(request: Request) -> SitzungsSpeicher:
    sitzungen: SitzungsSpeicher = request.app.state.sitzungen
    return sitzungen


def get_ratenbegrenzer(request: Request) -> Ratenbegrenzer:
    begrenzer: Ratenbegrenzer = request.app.state.ratenbegrenzer
    return begrenzer


def chat_rate_pruefen(
    request: Request, begrenzer: Annotated[Ratenbegrenzer, Depends(get_ratenbegrenzer)]
) -> None:
    pruefe_rate(request, begrenzer, "Chat")


# Wie bei der Wissenssuche: nur Leerzeichen gilt als leer.
Nachricht = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class ChatAnfrage(BaseModel):
    nachricht: Nachricht
    sitzung_id: uuid.UUID | None = None


class QuelleAntwort(BaseModel):
    dokument: str
    titel: str


class TerminVorschlag(BaseModel):
    typ: Literal["termin_vorschlag"] = "termin_vorschlag"
    slots: list[Slot]


class ChatAntwort(BaseModel):
    sitzung_id: str
    antwort: str
    kategorie: Kategorie
    quellen: list[QuelleAntwort]
    aktion: TerminVorschlag | None = None
    ki_hinweis: str = KI_HINWEIS


@router.post("/chat", response_model=ChatAntwort, dependencies=[Depends(chat_rate_pruefen)])
def chat(
    anfrage: ChatAnfrage,
    katalog: Katalog,
    session: DbSession,
    embedder: Annotated[Embedder, Depends(get_embedder)],
    provider: Annotated[LlmProvider, Depends(get_provider)],
    system_prompt: Annotated[str, Depends(get_system_prompt)],
    sitzungen: Annotated[SitzungsSpeicher, Depends(get_sitzungen)],
    terminsystem: TerminsystemDep,
) -> ChatAntwort:
    sitzung_id = str(anfrage.sitzung_id or uuid.uuid4())
    werkzeuge = Werkzeugkasten(katalog, session, embedder, terminsystem)
    try:
        ergebnis = run_chat(
            provider, system_prompt, sitzungen.verlauf(sitzung_id), anfrage.nachricht, werkzeuge
        )
    except LlmError as fehler:
        # Nur der Fehlertyp, kein Nachrichtentext (kann personenbezogene Daten enthalten).
        logger.warning("Chat: LLM-Anbieter fehlgeschlagen (%s)", redact(str(fehler)))
        return ChatAntwort(
            sitzung_id=sitzung_id, antwort=FEHLER_ANTWORT, kategorie="fehler", quellen=[]
        )
    sitzungen.speichern(sitzung_id, anfrage.nachricht, ergebnis.antwort)
    logger.info(
        "Chat: Nachricht mit %d Zeichen, %d Werkzeugaufrufe, %d Quellen",
        len(anfrage.nachricht),
        ergebnis.werkzeugaufrufe,
        len(ergebnis.quellen),
    )
    return ChatAntwort(
        sitzung_id=sitzung_id,
        antwort=ergebnis.antwort,
        kategorie=ergebnis.kategorie,
        quellen=[QuelleAntwort(dokument=q.dokument, titel=q.titel) for q in ergebnis.quellen],
        # Genau die Termine, die das Werkzeug geliefert hat – nie vom Modell formuliert.
        aktion=(
            TerminVorschlag(slots=werkzeuge.termin_vorschlag)
            if werkzeuge.termin_vorschlag is not None
            else None
        ),
    )
