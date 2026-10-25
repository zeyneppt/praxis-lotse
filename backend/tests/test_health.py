from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.db import database_reachable
from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    # Ohne Kontextmanager läuft der Lifespan (Migrationen) nicht.
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_ok(client: TestClient) -> None:
    app.dependency_overrides[database_reachable] = lambda: True
    app.dependency_overrides[get_settings] = lambda: Settings(llm_provider="ollama")

    antwort = client.get("/api/health")

    assert antwort.status_code == 200
    assert antwort.json() == {"status": "ok", "datenbank": "ok", "llm_provider": "ollama"}


def test_health_meldet_datenbankfehler_mit_503(client: TestClient) -> None:
    app.dependency_overrides[database_reachable] = lambda: False
    app.dependency_overrides[get_settings] = lambda: Settings(llm_provider="fake")

    antwort = client.get("/api/health")

    assert antwort.status_code == 503
    assert antwort.json()["datenbank"] == "fehler"
    assert antwort.json()["llm_provider"] == "fake"


def test_unbekannter_pfad_liefert_404(client: TestClient) -> None:
    assert client.get("/api/gibt-es-nicht").status_code == 404


def test_cors_erlaubt_frontend(client: TestClient) -> None:
    app.dependency_overrides[database_reachable] = lambda: True
    antwort = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert antwort.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_unbekannter_llm_provider_wird_abgelehnt() -> None:
    with pytest.raises(ValueError):
        Settings.model_validate({"llm_provider": "unbekannt"})
