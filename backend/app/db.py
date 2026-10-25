"""Datenbankverbindung und Migrationen."""

from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text

from app.config import get_settings

ALEMBIC_DIR = Path(__file__).resolve().parent.parent / "alembic"


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


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
