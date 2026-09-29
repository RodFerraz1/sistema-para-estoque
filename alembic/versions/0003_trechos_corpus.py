"""Create copilot.trechos_corpus for the RAG corpus embeddings.

Revision ID: 0003_trechos_corpus
Revises: 0002_politicas_compra
Create Date: 2026-09-29

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0003_trechos_corpus"
down_revision: Union[str, Sequence[str], None] = "0002_politicas_compra"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "trechos_corpus",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("documento", sa.Text, nullable=False),
        sa.Column("titulo", sa.Text, nullable=False),
        sa.Column("tipo", sa.Text, nullable=False),
        sa.Column("data", sa.Date, nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.Text), nullable=False),
        sa.Column("texto", sa.Text, nullable=False),
        sa.Column("hash_documento", sa.Text, nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column(
            "indexado_em",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema="copilot",
    )
    op.create_index(
        "trechos_corpus_documento_idx", "trechos_corpus", ["documento"], schema="copilot"
    )


def downgrade() -> None:
    op.drop_table("trechos_corpus", schema="copilot")
