"""Create copilot.sugestoes_fila, the approval queue of purchase suggestions.

Revision ID: 0007_sugestoes_fila
Revises: 0006_faixas_aprovacao
Create Date: 2026-09-30

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_sugestoes_fila"
down_revision: Union[str, Sequence[str], None] = "0006_faixas_aprovacao"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sugestoes_fila",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("sku_code", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("destaque", sa.Boolean, nullable=False),
        sa.Column("cobertura_na_chegada_sem_compra_meses", sa.Double, nullable=False),
        sa.Column("dados", postgresql.JSONB, nullable=False),
        sa.Column("faixa", postgresql.JSONB, nullable=False),
        sa.Column("decidido_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("decidido_por", sa.Text, nullable=True),
        sa.Column("quantidade_aprovada", sa.Integer, nullable=True),
        sa.Column("justificativa", sa.Text, nullable=True),
        sa.Column("motivo_rejeicao", sa.Text, nullable=True),
        sa.Column("pedido_compra_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pendente', 'aprovada', 'rejeitada', 'substituida')",
            name="sugestoes_fila_status_check",
        ),
        sa.CheckConstraint(
            "quantidade_aprovada IS NULL OR quantidade_aprovada > 0",
            name="sugestoes_fila_quantidade_aprovada_positiva",
        ),
        schema="copilot",
    )
    op.create_index(
        "sugestoes_fila_ordem_idx",
        "sugestoes_fila",
        ["status", sa.text("destaque DESC"), "cobertura_na_chegada_sem_compra_meses"],
        schema="copilot",
    )


def downgrade() -> None:
    op.drop_table("sugestoes_fila", schema="copilot")
