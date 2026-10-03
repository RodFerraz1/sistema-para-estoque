"""Create copilot.avisos, the sales team's notices about a SKU.

Revision ID: 0010_avisos
Revises: 0009_motivos_de_alerta
Create Date: 2026-10-01

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_avisos"
down_revision: Union[str, Sequence[str], None] = "0009_motivos_de_alerta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "avisos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sku_code", sa.Text, nullable=False),
        sa.Column("tipo", sa.Text, nullable=False),
        sa.Column("comentario", sa.Text, nullable=True),
        sa.Column("avisado_por", sa.Text, nullable=False),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("tipo IN ('acabou', 'vendendo_muito')", name="avisos_tipo_check"),
        sa.CheckConstraint("btrim(avisado_por) <> ''", name="avisos_avisado_por_check"),
        schema="copilot",
    )
    op.create_index("avisos_sku_code_criado_em_idx", "avisos", ["sku_code", "criado_em"], schema="copilot")


def downgrade() -> None:
    op.drop_table("avisos", schema="copilot")
