from collections.abc import Iterator
from typing import Any

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from app import db


@pytest.fixture(autouse=True)
def frische_engine() -> Iterator[None]:
    db.get_engine.cache_clear()
    yield
    db.get_engine.cache_clear()


def test_engine_setzt_connect_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    aufrufe: list[dict[str, Any]] = []

    def create_engine_merken(url: str, **kwargs: Any) -> object:
        aufrufe.append(kwargs)
        return object()

    monkeypatch.setattr(db, "create_engine", create_engine_merken)

    db.get_engine()

    assert aufrufe[0]["connect_args"] == {"connect_timeout": db.CONNECT_TIMEOUT_SECONDS}
    assert 0 < db.CONNECT_TIMEOUT_SECONDS <= 5


def test_database_reachable_meldet_fehler_statt_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class KaputteEngine:
        def connect(self) -> None:
            raise TimeoutError("connection timeout expired")

    monkeypatch.setattr(db, "get_engine", lambda: KaputteEngine())

    assert db.database_reachable() is False


def test_migrationsverzeichnis_wird_gefunden() -> None:
    # Schlägt fehl, wenn `app` aus site-packages statt aus dem Quellverzeichnis
    # importiert wird – dann zeigt ALEMBIC_DIR ins Leere.
    assert (db.ALEMBIC_DIR / "env.py").is_file()

    config = Config()
    config.set_main_option("script_location", str(db.ALEMBIC_DIR))
    assert ScriptDirectory.from_config(config).get_current_head() == "0003"
