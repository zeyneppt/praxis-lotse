"""FastAPI-Anwendung des Praxis-Lotse."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api_standorte import router as standorte_router
from app.config import LlmProvider, Settings, get_settings
from app.db import database_reachable, run_migrations
from app.standorte import load_katalog


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    run_migrations()
    app.state.standort_katalog = load_katalog(get_settings().data_dir)
    yield


app = FastAPI(title="Praxis-Lotse", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(standorte_router)


class HealthResponse(BaseModel):
    status: str
    datenbank: str
    llm_provider: LlmProvider


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
