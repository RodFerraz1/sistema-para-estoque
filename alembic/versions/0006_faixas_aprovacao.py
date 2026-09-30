"""Add approval band limits to copilot.politicas_compra.

Revision ID: 0006_faixas_aprovacao
Revises: 0005_sinais_e_citacoes
Create Date: 2026-09-30

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_faixas_aprovacao"
down_revision: Union[str, Sequence[str], None] = "0005_sinais_e_citacoes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Limites de `politicas/aprovacao-compras.md` v2, em reais inteiros.
_FAIXAS = {
    "faixa_1_ate_reais": 15_000,
    "faixa_2_ate_reais": 60_000,
    "faixa_3_ate_reais": 150_000,
}


def upgrade() -> None:
    for coluna, padrao in _FAIXAS.items():
        op.add_column(
            "politicas_compra",
            sa.Column(coluna, sa.Integer, nullable=False, server_default=str(padrao)),
            schema="copilot",
        )
        # O padrão só preenche as versões existentes; como nas outras colunas, quem grava informa o valor.
        op.alter_column("politicas_compra", coluna, server_default=None, schema="copilot")


def downgrade() -> None:
    for coluna in reversed(_FAIXAS):
        op.drop_column("politicas_compra", coluna, schema="copilot")
