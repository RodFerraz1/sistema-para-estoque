"""Late deliveries as an alert reason and copilot.cobrancas_entrega, the head buyer's delivery follow-ups.

`entrega_atrasada` becomes a valid alert reason. The default version (v1, while it still
has the previous default reasons) moves to the new default, `abaixo_do_piso_alerta` plus
`entrega_atrasada`. Versions saved by the buyer don't change.

A follow-up is for the whole purchase order and records the logged-in user. The ERP stays
read-only (ADR-0005): the new forecast lives here.

The downgrade drops the table, turns the default back and removes `entrega_atrasada` from
every version, since the old constraint doesn't know it.

Revision ID: 0017_entregas_atrasadas
Revises: 0016_categoria_banho
Create Date: 2026-10-04

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_entregas_atrasadas"
down_revision: Union[str, Sequence[str], None] = "0016_categoria_banho"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT = "politicas_compra_motivos_de_alerta_check"
_MOTIVOS_ANTIGOS = (
    "ruptura_antes_da_chegada",
    "viola_teto",
    "lead_time_observado_acima_do_contratado",
    "abaixo_pedido_minimo",
    "periodo_sazonal",
    "abaixo_do_piso_alerta",
)
_MOTIVOS_NOVOS = (*_MOTIVOS_ANTIGOS, "entrega_atrasada")
_PADRAO_ANTIGO = ("abaixo_do_piso_alerta",)
_PADRAO_NOVO = ("abaixo_do_piso_alerta", "entrega_atrasada")


def _array(valores: tuple[str, ...]) -> str:
    return "ARRAY[" + ", ".join(f"'{v}'" for v in valores) + "]::text[]"


def _trocar_constraint(motivos: tuple[str, ...]) -> None:
    op.drop_constraint(_CONSTRAINT, "politicas_compra", schema="copilot")
    op.create_check_constraint(
        _CONSTRAINT, "politicas_compra", f"motivos_de_alerta <@ {_array(motivos)}", schema="copilot"
    )


def upgrade() -> None:
    _trocar_constraint(_MOTIVOS_NOVOS)
    op.execute(
        f"""
        UPDATE copilot.politicas_compra SET motivos_de_alerta = {_array(_PADRAO_NOVO)}
        WHERE versao = 1 AND motivos_de_alerta = {_array(_PADRAO_ANTIGO)}
        """
    )

    op.create_table(
        "cobrancas_entrega",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pedido_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fornecedor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nova_previsao", sa.Date, nullable=True),
        sa.Column("comentario", sa.Text, nullable=True),
        sa.Column("cobrado_por", sa.Text, nullable=False),
        sa.Column(
            "usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("copilot.usuarios.id"), nullable=False
        ),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("btrim(cobrado_por) <> ''", name="cobrancas_entrega_cobrado_por_check"),
        schema="copilot",
    )
    op.create_index(
        "cobrancas_entrega_pedido_id_criado_em_idx", "cobrancas_entrega", ["pedido_id", "criado_em"], schema="copilot"
    )
    op.create_index("cobrancas_entrega_usuario_id_idx", "cobrancas_entrega", ["usuario_id"], schema="copilot")


def downgrade() -> None:
    op.drop_table("cobrancas_entrega", schema="copilot")
    op.execute(
        f"""
        UPDATE copilot.politicas_compra SET motivos_de_alerta = {_array(_PADRAO_ANTIGO)}
        WHERE versao = 1 AND motivos_de_alerta = {_array(_PADRAO_NOVO)}
        """
    )
    op.execute(
        "UPDATE copilot.politicas_compra "
        "SET motivos_de_alerta = array_remove(motivos_de_alerta, 'entrega_atrasada')"
    )
    _trocar_constraint(_MOTIVOS_ANTIGOS)
