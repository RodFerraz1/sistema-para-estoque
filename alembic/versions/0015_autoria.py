"""Add usuario_id to copilot.avisos, copilot.decisoes_compra and copilot.registros_decisao.

Notices, purchase decisions and chat records now record the logged-in user (ADR-0007).
`avisado_por` and `decidido_por` stay as the name written at the time. Rows from before
the login keep `usuario_id` null.

Revision ID: 0015_autoria
Revises: 0014_usuarios
Create Date: 2026-10-03

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_autoria"
down_revision: Union[str, Sequence[str], None] = "0014_usuarios"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABELAS = ("avisos", "decisoes_compra", "registros_decisao")


def upgrade() -> None:
    for tabela in _TABELAS:
        op.add_column(
            tabela,
            sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("copilot.usuarios.id"), nullable=True),
            schema="copilot",
        )
        op.create_index(f"{tabela}_usuario_id_idx", tabela, ["usuario_id"], schema="copilot")


def downgrade() -> None:
    for tabela in _TABELAS:
        op.drop_index(f"{tabela}_usuario_id_idx", table_name=tabela, schema="copilot")
        op.drop_column(tabela, "usuario_id", schema="copilot")
