"""Add usuario_destino to copilot.episodios_alerta.

Most episodes go to a role. The decision about a sales notice (and, later, the shelf check
about an empty-shelf notice) goes to one person: the author of the notice. Such an episode
keeps the target role and also the target user, and only that user sees it.

Revision ID: 0021_notificacao_para_uma_pessoa
Revises: 0020_verificacoes_gondola
Create Date: 2026-10-04

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_notificacao_para_uma_pessoa"
down_revision: Union[str, Sequence[str], None] = "0020_verificacoes_gondola"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "episodios_alerta",
        sa.Column(
            "usuario_destino", postgresql.UUID(as_uuid=True), sa.ForeignKey("copilot.usuarios.id"), nullable=True
        ),
        schema="copilot",
    )
    op.create_index(
        "episodios_alerta_usuario_destino_aberto_em_idx",
        "episodios_alerta",
        ["usuario_destino", "aberto_em"],
        schema="copilot",
    )


def downgrade() -> None:
    op.execute("DELETE FROM copilot.episodios_alerta WHERE usuario_destino IS NOT NULL")
    op.drop_index(
        "episodios_alerta_usuario_destino_aberto_em_idx", table_name="episodios_alerta", schema="copilot"
    )
    op.drop_column("episodios_alerta", "usuario_destino", schema="copilot")
