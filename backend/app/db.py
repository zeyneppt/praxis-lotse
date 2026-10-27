"""Datenbankverbindung und Migrationen."""

from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text

from app.config import get_settings

# Die Migrationen liegen neben dem Paket (backend/alembic). Das Backend muss daher
# aus dem Quellverzeichnis laufen (im Container: editable install, siehe Dockerfile).
ALEMBIC_DIR = Path(__file__).resolve().parent.parent / "alembic"

# Ein hängender DB-Host soll /api/health nicht blockieren, sondern schnell 503 liefern.
CONNECT_TIMEOUT_SECONDS = 3


@lru_cache
def get_engine() -> Engine:
    return create_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        # Fehlermeldungen ohne SQL-Parameter: Sie enthielten sonst z. B. Name und Telefon
        # aus Terminanfragen, und unbehandelte Fehler landen im Log.
        hide_parameters=True,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


def database_reachable() -> bool:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


def run_migrations() -> None:
    config = Config()
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    command.upgrade(config, "head")
