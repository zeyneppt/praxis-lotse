"""FastAPI-Anwendung des Praxis-Lotse."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api_chat import router as chat_router
from app.api_standorte import router as standorte_router
from app.api_termine import router as termine_router
from app.api_wissen import router as wissen_router
from app.chat import load_system_prompt
from app.config import LlmProviderName, Settings, get_settings
from app.db import database_reachable, get_engine, run_migrations
from app.embeddings import FastEmbedder
from app.llm import LlmConfigError, check_provider, create_provider
from app.logging import configure_logging
from app.ratenbegrenzung import MAX_TERMINANFRAGEN_PRO_MINUTE, Ratenbegrenzer
from app.sitzungen import SitzungsSpeicher
from app.standorte import load_katalog
from app.termine import SimuliertesTerminsystem, Terminsystem

configure_logging()
logger = logging.getLogger(__name__)

LOESCHLAUF_INTERVALL_SEKUNDEN = 3600


async def loeschfrist_durchsetzen(terminsystem: Terminsystem) -> None:
    """Löscht alte Terminanfragen beim Start und danach stündlich (Spec 005)."""
    while True:
        try:
            anzahl = await asyncio.to_thread(terminsystem.alte_anfragen_loeschen)
            logger.info("Löschfrist: %d alte Terminanfragen gelöscht", anzahl)
        except Exception as fehler:
            # Nur der Typ: Die Meldung könnte Werte aus der Tabelle enthalten.
            logger.warning("Löschfrist: Löschlauf fehlgeschlagen (%s)", type(fehler).__name__)
        await asyncio.sleep(LOESCHLAUF_INTERVALL_SEKUNDEN)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    try:
        app.state.llm_provider = create_provider(settings)
    except LlmConfigError as fehler:
        logger.error("Backend startet nicht: %s", fehler)
        raise
    check_provider(app.state.llm_provider, settings)
    app.state.system_prompt = load_system_prompt()
    app.state.sitzungen = SitzungsSpeicher()
    app.state.ratenbegrenzer = Ratenbegrenzer()
    app.state.termine_ratenbegrenzer = Ratenbegrenzer(MAX_TERMINANFRAGEN_PRO_MINUTE)
    run_migrations()
    app.state.standort_katalog = load_katalog(settings.data_dir)
    app.state.terminsystem = SimuliertesTerminsystem(app.state.standort_katalog, get_engine())
    loeschjob = asyncio.create_task(loeschfrist_durchsetzen(app.state.terminsystem))
    # Beim Start laden, nicht beim ersten Request (das Modell liegt seit dem Build lokal).
    app.state.embedder = FastEmbedder(settings.embedding_model)
    yield
    loeschjob.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await loeschjob


app = FastAPI(title="Praxis-Lotse", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_error_without_input(
    request: Request, fehler: RequestValidationError
) -> JSONResponse:
    """422 wie bei FastAPI, aber ohne `input` und `ctx`.

    Die Standardantwort wiederholt die Eingabe im Klartext, z. B. Telefon oder
    Geburtsdatum einer Terminanfrage oder eine Chat-Nachricht.
    """
    details = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in fehler.errors()]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": jsonable_encoder(details)},
    )


app.include_router(standorte_router)
app.include_router(wissen_router)
app.include_router(chat_router)
app.include_router(termine_router)


class HealthResponse(BaseModel):
    status: str
    datenbank: str
    llm_provider: LlmProviderName


@app.get("/api/health", response_model=HealthResponse)
def health(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    db_ok: Annotated[bool, Depends(database_reachable)],
) -> HealthResponse:
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok",
        datenbank="ok" if db_ok else "fehler",
        llm_provider=settings.llm_provider,
    )
