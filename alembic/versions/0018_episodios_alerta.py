"""Create copilot.episodios_alerta and the users' notification cursor.

An alert episode is the interval in which a condition holds for a SKU (or for a purchase
order, for a late delivery). The sweep opens and closes them; one-off events, like a sales
team notice, are stored already closed. The partial unique index keeps two open episodes
of the same condition from existing. A notification is an episode seen by a user of the
target role: unread while it was opened after the user's `notificacoes_vistas_ate`.

Revision ID: 0018_episodios_alerta
Revises: 0017_entregas_atrasadas
Create Date: 2026-10-04

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_episodios_alerta"
down_revision: Union[str, Sequence[str], None] = "0017_entregas_atrasadas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TIPOS = (
    "ruptura",
    "entrega_atrasada",
    "aviso",
    "queda_de_venda",
    "estoque_divergente",
    "decisao_sobre_aviso",
    "gondola_vazia",
    "verificacao_sobre_aviso",
)
_PAPEIS = ("comprador", "vendas", "reposicao", "admin")


def _lista(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def upgrade() -> None:
    op.add_column(
        "usuarios", sa.Column("notificacoes_vistas_ate", sa.TIMESTAMP(timezone=True), nullable=True), schema="copilot"
    )
    op.create_table(
        "episodios_alerta",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tipo", sa.Text, nullable=False),
        sa.Column("sku_code", sa.Text, nullable=True),
        sa.Column("pedido_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("papel_destino", sa.Text, nullable=False),
        sa.Column("aberto_em", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("fechado_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("detalhe", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint(f"tipo IN ({_lista(_TIPOS)})", name="episodios_alerta_tipo_check"),
        sa.CheckConstraint(f"papel_destino IN ({_lista(_PAPEIS)})", name="episodios_alerta_papel_destino_check"),
        sa.CheckConstraint(
            "fechado_em IS NULL OR fechado_em >= aberto_em", name="episodios_alerta_fechado_em_check"
        ),
        schema="copilot",
    )
    op.execute(
        "CREATE UNIQUE INDEX episodios_alerta_aberto_unico ON copilot.episodios_alerta "
        "(tipo, sku_code, pedido_id) NULLS NOT DISTINCT WHERE fechado_em IS NULL"
    )
    op.create_index(
        "episodios_alerta_papel_destino_aberto_em_idx",
        "episodios_alerta",
        ["papel_destino", "aberto_em"],
        schema="copilot",
    )


def downgrade() -> None:
    op.drop_table("episodios_alerta", schema="copilot")
    op.drop_column("usuarios", "notificacoes_vistas_ate", schema="copilot")
