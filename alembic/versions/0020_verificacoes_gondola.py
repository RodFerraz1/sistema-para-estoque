"""copilot.verificacoes_gondola, what the shelf restocker found, and divergent stock as an alert reason.

A shelf check records the result (`repus`, `estava_na_gondola` or
`sem_estoque_no_deposito`), an optional comment, the ERP available quantity at that moment
and the logged-in user. `estoque_divergente` becomes a valid alert reason. The default
version (v1, while it still has the previous default reasons) moves to the new default,
which adds `estoque_divergente`. Versions saved by the buyer don't change.

The downgrade drops the table, turns the default back and removes `estoque_divergente` from
every version, since the old constraint doesn't know it.

Revision ID: 0020_verificacoes_gondola
Revises: 0019_queda_de_venda
Create Date: 2026-10-04

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_verificacoes_gondola"
down_revision: Union[str, Sequence[str], None] = "0019_queda_de_venda"
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
    "entrega_atrasada",
)
_MOTIVOS_NOVOS = (*_MOTIVOS_ANTIGOS, "estoque_divergente")
_PADRAO_ANTIGO = ("abaixo_do_piso_alerta", "entrega_atrasada")
_PADRAO_NOVO = ("abaixo_do_piso_alerta", "entrega_atrasada", "estoque_divergente")
_RESULTADOS = ("repus", "estava_na_gondola", "sem_estoque_no_deposito")


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
        "verificacoes_gondola",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sku_code", sa.Text, nullable=False),
        sa.Column("resultado", sa.Text, nullable=False),
        sa.Column("comentario", sa.Text, nullable=True),
        sa.Column("disponivel_no_erp", sa.Integer, nullable=False),
        sa.Column("verificado_por", sa.Text, nullable=False),
        sa.Column(
            "usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("copilot.usuarios.id"), nullable=False
        ),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "resultado IN (" + ", ".join(f"'{r}'" for r in _RESULTADOS) + ")",
            name="verificacoes_gondola_resultado_check",
        ),
        sa.CheckConstraint("btrim(verificado_por) <> ''", name="verificacoes_gondola_verificado_por_check"),
        schema="copilot",
    )
    op.create_index(
        "verificacoes_gondola_sku_code_criado_em_idx",
        "verificacoes_gondola",
        ["sku_code", "criado_em"],
        schema="copilot",
    )
    op.create_index("verificacoes_gondola_usuario_id_idx", "verificacoes_gondola", ["usuario_id"], schema="copilot")


def downgrade() -> None:
    op.drop_table("verificacoes_gondola", schema="copilot")
    op.execute(
        f"""
        UPDATE copilot.politicas_compra SET motivos_de_alerta = {_array(_PADRAO_ANTIGO)}
        WHERE versao = 1 AND motivos_de_alerta = {_array(_PADRAO_NOVO)}
        """
    )
    op.execute(
        "UPDATE copilot.politicas_compra "
        "SET motivos_de_alerta = array_remove(motivos_de_alerta, 'estoque_divergente')"
    )
    _trocar_constraint(_MOTIVOS_ANTIGOS)
