"""Create copilot.politicas_compra with v1 from policy v3.

Revision ID: 0002_politicas_compra
Revises: 0001_erp_schema
Create Date: 2026-09-29

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_politicas_compra"
down_revision: Union[str, Sequence[str], None] = "0001_erp_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _in(coluna: str, valores: tuple[str, ...]) -> str:
    return f"{coluna} IN (" + ", ".join(f"'{v}'" for v in valores) + ")"


def upgrade() -> None:
    op.create_table(
        "politicas_compra",
        sa.Column("versao", sa.Integer, sa.Identity(always=True), primary_key=True),
        sa.Column(
            "criada_em",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("teto_meses", sa.Float, nullable=False),
        sa.Column("piso_alerta_dias", sa.Integer, nullable=False),
        sa.Column("piso_reposicao_dias", sa.Integer, nullable=False),
        sa.Column("ciclo_compra_meses", sa.Float, nullable=False),
        sa.Column("lead_time_base", sa.Text, nullable=False),
        sa.Column("criterio_fornecedor", sa.Text, nullable=False),
        sa.Column("sazonalidade_modo", sa.Text, nullable=False),
        sa.Column("meses_quentes", postgresql.ARRAY(sa.Integer), nullable=False),
        sa.Column("extra_sazonal_meses", sa.Float, nullable=False),
        sa.Column("dias_historico_minimo", sa.Integer, nullable=False),
        sa.CheckConstraint(
            _in("lead_time_base", ("observado", "contratado", "maior")),
            name="politicas_compra_lead_time_base_check",
        ),
        sa.CheckConstraint(
            _in("criterio_fornecedor", ("menor_preco", "menor_lead_time")),
            name="politicas_compra_criterio_fornecedor_check",
        ),
        sa.CheckConstraint(
            _in("sazonalidade_modo", ("ignorar", "alertar")),
            name="politicas_compra_sazonalidade_modo_check",
        ),
        schema="copilot",
    )

    op.execute(
        """
        INSERT INTO copilot.politicas_compra (
            teto_meses, piso_alerta_dias, piso_reposicao_dias, ciclo_compra_meses,
            lead_time_base, criterio_fornecedor, sazonalidade_modo,
            meses_quentes, extra_sazonal_meses, dias_historico_minimo
        ) VALUES (
            3.0, 20, 30, 1.0,
            'observado', 'menor_preco', 'alertar',
            ARRAY[5, 6, 11, 12], 2.0, 60
        )
        """
    )


def downgrade() -> None:
    op.drop_table("politicas_compra", schema="copilot")
