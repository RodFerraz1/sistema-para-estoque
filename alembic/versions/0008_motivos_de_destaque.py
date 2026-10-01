"""Add the approval queue highlight reasons to copilot.politicas_compra.

Revision ID: 0008_motivos_de_destaque
Revises: 0007_sugestoes_fila
Create Date: 2026-09-30

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_motivos_de_destaque"
down_revision: Union[str, Sequence[str], None] = "0007_sugestoes_fila"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MOTIVOS = (
    "ruptura_antes_da_chegada",
    "viola_teto",
    "lead_time_observado_acima_do_contratado",
    "abaixo_pedido_minimo",
    "periodo_sazonal",
    "atraso_do_fornecedor",
    "demanda_sazonal",
    "encalhe",
)
_PADRAO = "{ruptura_antes_da_chegada,viola_teto}"


def upgrade() -> None:
    op.add_column(
        "politicas_compra",
        sa.Column(
            "motivos_de_destaque",
            postgresql.ARRAY(sa.Text),
            nullable=False,
            server_default=_PADRAO,
        ),
        schema="copilot",
    )
    # O padrão só preenche as versões existentes; como nas outras colunas, quem grava informa o valor.
    op.alter_column("politicas_compra", "motivos_de_destaque", server_default=None, schema="copilot")
    op.create_check_constraint(
        "politicas_compra_motivos_de_destaque_check",
        "politicas_compra",
        "motivos_de_destaque <@ ARRAY[" + ", ".join(f"'{m}'" for m in _MOTIVOS) + "]::text[]",
        schema="copilot",
    )


def downgrade() -> None:
    op.drop_column("politicas_compra", "motivos_de_destaque", schema="copilot")
