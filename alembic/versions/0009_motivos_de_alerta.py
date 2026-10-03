"""Drop the approval queue and bands; highlight reasons become alert reasons (ADR-0005).

Remove `copilot.sugestoes_fila` and the band limits of `copilot.politicas_compra`,
rename `motivos_de_destaque` to `motivos_de_alerta` in every version (dropping the
corpus reasons and adding `abaixo_do_piso_alerta`). The default version (v1, while
it still has the original values) moves to the new default: a 2-month purchase
cycle and `ruptura_antes_da_chegada` plus `abaixo_do_piso_alerta`.

Revision ID: 0009_motivos_de_alerta
Revises: 0008_motivos_de_destaque
Create Date: 2026-10-01

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_motivos_de_alerta"
down_revision: Union[str, Sequence[str], None] = "0008_motivos_de_destaque"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MOTIVOS_DE_ALERTA = (
    "ruptura_antes_da_chegada",
    "viola_teto",
    "lead_time_observado_acima_do_contratado",
    "abaixo_pedido_minimo",
    "periodo_sazonal",
    "abaixo_do_piso_alerta",
)
_MOTIVOS_DE_DESTAQUE = (
    "ruptura_antes_da_chegada",
    "viola_teto",
    "lead_time_observado_acima_do_contratado",
    "abaixo_pedido_minimo",
    "periodo_sazonal",
    "atraso_do_fornecedor",
    "demanda_sazonal",
    "encalhe",
)
_PADRAO_ANTIGO = ("ruptura_antes_da_chegada", "viola_teto")
_PADRAO_NOVO = ("ruptura_antes_da_chegada", "abaixo_do_piso_alerta")
_MOTIVOS_DO_CORPUS = ("atraso_do_fornecedor", "demanda_sazonal", "encalhe")
_FAIXAS = {
    "faixa_1_ate_reais": 15_000,
    "faixa_2_ate_reais": 60_000,
    "faixa_3_ate_reais": 150_000,
}


def _array(valores: tuple[str, ...]) -> str:
    return "ARRAY[" + ", ".join(f"'{v}'" for v in valores) + "]::text[]"


def upgrade() -> None:
    op.drop_table("sugestoes_fila", schema="copilot")

    for coluna in _FAIXAS:
        op.drop_column("politicas_compra", coluna, schema="copilot")

    op.drop_constraint(
        "politicas_compra_motivos_de_destaque_check", "politicas_compra", schema="copilot"
    )
    op.alter_column(
        "politicas_compra", "motivos_de_destaque", new_column_name="motivos_de_alerta", schema="copilot"
    )
    # A ordem dos motivos que ficam é mantida, e o novo entra no fim.
    op.execute(
        f"""
        UPDATE copilot.politicas_compra SET motivos_de_alerta = ARRAY(
            SELECT m FROM unnest(motivos_de_alerta) WITH ORDINALITY AS t(m, i)
            WHERE m <> ALL({_array(_MOTIVOS_DO_CORPUS)})
            ORDER BY i
        ) || ARRAY['abaixo_do_piso_alerta']::text[]
        """
    )
    op.create_check_constraint(
        "politicas_compra_motivos_de_alerta_check",
        "politicas_compra",
        f"motivos_de_alerta <@ {_array(_MOTIVOS_DE_ALERTA)}",
        schema="copilot",
    )

    op.execute(
        f"""
        UPDATE copilot.politicas_compra
        SET ciclo_compra_meses = 2.0, motivos_de_alerta = {_array(_PADRAO_NOVO)}
        WHERE versao = 1 AND ciclo_compra_meses = 1.0
          AND motivos_de_alerta = {_array((*_PADRAO_ANTIGO, "abaixo_do_piso_alerta"))}
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE copilot.politicas_compra
        SET ciclo_compra_meses = 1.0,
            motivos_de_alerta = {_array((*_PADRAO_ANTIGO, "abaixo_do_piso_alerta"))}
        WHERE versao = 1 AND ciclo_compra_meses = 2.0 AND motivos_de_alerta = {_array(_PADRAO_NOVO)}
        """
    )

    op.drop_constraint(
        "politicas_compra_motivos_de_alerta_check", "politicas_compra", schema="copilot"
    )
    op.execute(
        "UPDATE copilot.politicas_compra "
        "SET motivos_de_alerta = array_remove(motivos_de_alerta, 'abaixo_do_piso_alerta')"
    )
    op.alter_column(
        "politicas_compra", "motivos_de_alerta", new_column_name="motivos_de_destaque", schema="copilot"
    )
    op.create_check_constraint(
        "politicas_compra_motivos_de_destaque_check",
        "politicas_compra",
        f"motivos_de_destaque <@ {_array(_MOTIVOS_DE_DESTAQUE)}",
        schema="copilot",
    )

    for coluna, padrao in _FAIXAS.items():
        op.add_column(
            "politicas_compra",
            sa.Column(coluna, sa.Integer, nullable=False, server_default=str(padrao)),
            schema="copilot",
        )
        op.alter_column("politicas_compra", coluna, server_default=None, schema="copilot")

    op.create_table(
        "sugestoes_fila",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("sku_code", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("destaque", sa.Boolean, nullable=False),
        sa.Column("cobertura_na_chegada_sem_compra_meses", sa.Double, nullable=False),
        sa.Column("dados", postgresql.JSONB, nullable=False),
        sa.Column("faixa", postgresql.JSONB, nullable=False),
        sa.Column("decidido_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("decidido_por", sa.Text, nullable=True),
        sa.Column("quantidade_aprovada", sa.Integer, nullable=True),
        sa.Column("justificativa", sa.Text, nullable=True),
        sa.Column("motivo_rejeicao", sa.Text, nullable=True),
        sa.Column("pedido_compra_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pendente', 'aprovada', 'rejeitada', 'substituida')",
            name="sugestoes_fila_status_check",
        ),
        sa.CheckConstraint(
            "quantidade_aprovada IS NULL OR quantidade_aprovada > 0",
            name="sugestoes_fila_quantidade_aprovada_positiva",
        ),
        schema="copilot",
    )
    op.create_index(
        "sugestoes_fila_ordem_idx",
        "sugestoes_fila",
        ["status", sa.text("destaque DESC"), "cobertura_na_chegada_sem_compra_meses"],
        schema="copilot",
    )
