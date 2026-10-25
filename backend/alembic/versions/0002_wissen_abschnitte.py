"""Tabelle wissen_abschnitte für die Wissensbasis

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-25
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# Dimension von paraphrase-multilingual-MiniLM-L12-v2 (Standard aus .env.example).
EMBEDDING_DIM = 384


def upgrade() -> None:
    op.create_table(
        "wissen_abschnitte",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("dokument", sa.Text, nullable=False),
        sa.Column("titel", sa.Text, nullable=False),
        sa.Column("abschnitt", sa.Text, nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("fachrichtungen", postgresql.ARRAY(sa.Text), nullable=False),
        sa.Column("inhalt_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
    )
    op.create_index("ix_wissen_abschnitte_dokument", "wissen_abschnitte", ["dokument"])
    op.create_index(
        "ix_wissen_abschnitte_embedding",
        "wissen_abschnitte",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_table("wissen_abschnitte")
