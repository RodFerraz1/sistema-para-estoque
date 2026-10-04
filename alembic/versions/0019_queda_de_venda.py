"""Sales drop detection parameters in the purchase policy (spec 09, ADR-0003).

Add `dias_observados_queda`, `venda_diaria_minima_queda` and `limiar_queda` to every
version of `copilot.politicas_compra`, with the defaults of the spec (2 days, 1 unit per
day, 0.01), to be validated with the buyer.

Revision ID: 0019_queda_de_venda
Revises: 0018_episodios_alerta
Create Date: 2026-10-04

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_queda_de_venda"
down_revision: Union[str, Sequence[str], None] = "0018_episodios_alerta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUNAS = (
    ("dias_observados_queda", sa.Integer, "2"),
    ("venda_diaria_minima_queda", sa.Float, "1.0"),
    ("limiar_queda", sa.Float, "0.01"),
)


def upgrade() -> None:
    for coluna, tipo, padrao in _COLUNAS:
        op.add_column(
            "politicas_compra",
            sa.Column(coluna, tipo, nullable=False, server_default=padrao),
            schema="copilot",
        )
        op.alter_column("politicas_compra", coluna, server_default=None, schema="copilot")


def downgrade() -> None:
    for coluna, _, _ in reversed(_COLUNAS):
        op.drop_column("politicas_compra", coluna, schema="copilot")
