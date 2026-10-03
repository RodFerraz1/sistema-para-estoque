"""Create copilot.decisoes_compra, the head buyer's purchase decisions (ADR-0005).

Revision ID: 0011_decisoes_compra
Revises: 0010_avisos
Create Date: 2026-10-01

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_decisoes_compra"
down_revision: Union[str, Sequence[str], None] = "0010_avisos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "decisoes_compra",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sku_code", sa.Text, nullable=False),
        sa.Column("tipo", sa.Text, nullable=False),
        sa.Column("quantidade", sa.Integer, nullable=True),
        sa.Column("motivo", sa.Text, nullable=True),
        sa.Column("comentario", sa.Text, nullable=True),
        sa.Column("decidido_por", sa.Text, nullable=False),
        sa.Column("quantidade_sugerida", sa.Integer, nullable=False),
        sa.Column("politica_versao", sa.Integer, nullable=False),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "tipo IN ('vou_comprar', 'negociando', 'nao_comprar_agora')", name="decisoes_compra_tipo_check"
        ),
        # As mesmas regras que o service valida.
        sa.CheckConstraint(
            "(tipo = 'vou_comprar') = (quantidade IS NOT NULL) AND (quantidade IS NULL OR quantidade > 0)",
            name="decisoes_compra_quantidade_check",
        ),
        sa.CheckConstraint(
            "tipo <> 'nao_comprar_agora' OR btrim(coalesce(motivo, '')) <> ''",
            name="decisoes_compra_motivo_check",
        ),
        sa.CheckConstraint("btrim(decidido_por) <> ''", name="decisoes_compra_decidido_por_check"),
        sa.CheckConstraint("quantidade_sugerida >= 0", name="decisoes_compra_quantidade_sugerida_check"),
        schema="copilot",
    )
    op.create_index(
        "decisoes_compra_sku_code_criado_em_idx", "decisoes_compra", ["sku_code", "criado_em"], schema="copilot"
    )


def downgrade() -> None:
    op.drop_table("decisoes_compra", schema="copilot")
