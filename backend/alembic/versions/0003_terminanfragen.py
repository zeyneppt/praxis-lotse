"""Tabelle terminanfragen für das simulierte Terminsystem

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "terminanfragen",
        sa.Column("anfrage_id", sa.Uuid, primary_key=True),
        # Ein Termin kann nur einmal angefragt werden.
        sa.Column("slot_id", sa.Text, nullable=False, unique=True),
        sa.Column("standort_id", sa.Text, nullable=False),
        sa.Column("fachrichtung", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("geburtsdatum", sa.Date, nullable=False),
        sa.Column("telefon", sa.Text, nullable=False),
        sa.Column("erstellt_am", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_terminanfragen_erstellt_am", "terminanfragen", ["erstellt_am"])


def downgrade() -> None:
    op.drop_table("terminanfragen")
