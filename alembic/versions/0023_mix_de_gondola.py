"""Shelf mix: `dias_mix_gondola` in the purchase policy and copilot.capacidades_gondola.

Add `dias_mix_gondola` to every version of `copilot.politicas_compra`, with the default of
the spec (90 open days), to be validated with the buyer. `capacidades_gondola` keeps how many
pieces of a catalog product fit on its shelf, as told by the stocker: one row per product,
the last one wins.

Revision ID: 0023_mix_de_gondola
Revises: 0022_setores_e_avisos_gondola
Create Date: 2026-10-04

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023_mix_de_gondola"
down_revision: Union[str, Sequence[str], None] = "0022_setores_e_avisos_gondola"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "politicas_compra",
        sa.Column("dias_mix_gondola", sa.Integer, nullable=False, server_default="90"),
        schema="copilot",
    )
    op.alter_column("politicas_compra", "dias_mix_gondola", server_default=None, schema="copilot")

    op.create_table(
        "capacidades_gondola",
        sa.Column("produto_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("capacidade", sa.Integer, nullable=False),
        sa.Column(
            "usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("copilot.usuarios.id"), nullable=False
        ),
        sa.Column(
            "atualizado_em", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("capacidade > 0", name="capacidades_gondola_capacidade_check"),
        schema="copilot",
    )


def downgrade() -> None:
    op.drop_table("capacidades_gondola", schema="copilot")
    op.drop_column("politicas_compra", "dias_mix_gondola", schema="copilot")
