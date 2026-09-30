"""Create copilot.registros_decisao for the chat decision log.

Revision ID: 0004_registros_decisao
Revises: 0003_trechos_corpus
Create Date: 2026-09-30

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_registros_decisao"
down_revision: Union[str, Sequence[str], None] = "0003_trechos_corpus"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "registros_decisao",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("pergunta", sa.Text, nullable=False),
        sa.Column("intencao", sa.Text, nullable=False),
        sa.Column("confianca", sa.Double, nullable=False),
        sa.Column("faixa", sa.Text, nullable=False),
        sa.Column("acao", sa.Text, nullable=False),
        sa.Column("skus", postgresql.ARRAY(sa.Text), nullable=False),
        sa.Column("entendimento", postgresql.JSONB, nullable=False),
        sa.Column("trechos", postgresql.ARRAY(sa.Text), nullable=False),
        sa.Column("redator", sa.Text, nullable=True),
        sa.Column("resposta", sa.Text, nullable=False),
        sa.Column("duracao_ms", sa.Integer, nullable=False),
        schema="copilot",
    )
    op.create_index(
        "registros_decisao_criado_em_idx", "registros_decisao", ["criado_em"], schema="copilot"
    )


def downgrade() -> None:
    op.drop_table("registros_decisao", schema="copilot")
