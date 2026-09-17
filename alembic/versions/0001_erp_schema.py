"""Create erp and copilot schemas plus erp tables.

Revision ID: 0001_erp_schema
Revises:
Create Date: 2026-09-16

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_erp_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MOVIMENTACAO_TIPOS = (
    "entrada_compra",
    "saida_venda",
    "ajuste_positivo",
    "ajuste_negativo",
    "devolucao",
)

PEDIDO_STATUS = (
    "rascunho",
    "aprovado",
    "enviado",
    "recebido_parcial",
    "recebido_total",
    "cancelado",
)


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS erp")
    op.execute("CREATE SCHEMA IF NOT EXISTS copilot")

    op.execute(
        "CREATE TYPE erp.movimentacao_tipo AS ENUM ("
        + ", ".join(f"'{v}'" for v in MOVIMENTACAO_TIPOS)
        + ")"
    )
    op.execute(
        "CREATE TYPE erp.pedido_compra_status AS ENUM ("
        + ", ".join(f"'{v}'" for v in PEDIDO_STATUS)
        + ")"
    )

    op.create_table(
        "produtos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("nome", sa.Text, nullable=False),
        sa.Column("categoria", sa.Text, nullable=False),
        sa.Column("descricao", sa.Text, nullable=True),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "categoria IN ('felpudo', 'jogo_cama', 'mesa', 'cozinha')",
            name="produtos_categoria_check",
        ),
        schema="erp",
    )

    op.create_table(
        "skus",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "produto_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("erp.produtos.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sku_code", sa.Text, nullable=False, unique=True),
        sa.Column("cor", sa.Text, nullable=False),
        sa.Column("tamanho", sa.Text, nullable=False),
        sa.Column("gramatura", sa.Integer, nullable=True),
        sa.Column("material", sa.Text, nullable=True),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema="erp",
    )
    op.create_index("ix_erp_skus_produto_id", "skus", ["produto_id"], schema="erp")

    op.create_table(
        "fornecedores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("nome", sa.Text, nullable=False),
        sa.Column("cnpj", sa.Text, nullable=False),
        sa.Column("prazo_pagamento_padrao", sa.Text, nullable=False),
        sa.Column("pedido_minimo_reais", sa.Integer, nullable=False),
        sa.Column("lead_time_dias_contratado", sa.Integer, nullable=False),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema="erp",
    )

    op.create_table(
        "fornecedores_skus",
        sa.Column(
            "fornecedor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("erp.fornecedores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sku_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("erp.skus.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("preco_unitario_atual", sa.Integer, nullable=False),
        sa.Column("moq_unidades", sa.Integer, nullable=False),
        sa.Column("lead_time_dias_observado", sa.Integer, nullable=True),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "atualizado_em",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint(
            "fornecedor_id", "sku_id", name="pk_fornecedores_skus"
        ),
        schema="erp",
    )

    op.create_table(
        "estoque_snapshot",
        sa.Column(
            "sku_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("erp.skus.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("quantidade_disponivel", sa.Integer, nullable=False),
        sa.Column(
            "quantidade_reservada",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "atualizado_em",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema="erp",
    )

    op.create_table(
        "movimentacoes_estoque",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "sku_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("erp.skus.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "tipo",
            postgresql.ENUM(
                *MOVIMENTACAO_TIPOS,
                name="movimentacao_tipo",
                schema="erp",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("quantidade", sa.Integer, nullable=False),
        sa.Column("data", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("referencia_tipo", sa.Text, nullable=True),
        sa.Column(
            "referencia_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("observacao", sa.Text, nullable=True),
        sa.CheckConstraint("quantidade > 0", name="movimentacoes_quantidade_positiva"),
        schema="erp",
    )
    op.create_index(
        "ix_erp_movimentacoes_sku_data",
        "movimentacoes_estoque",
        ["sku_id", "data"],
        schema="erp",
    )

    op.create_table(
        "vendas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "sku_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("erp.skus.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantidade", sa.Integer, nullable=False),
        sa.Column("valor_unitario_reais", sa.Integer, nullable=False),
        sa.Column("data", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("cliente_ref", sa.Text, nullable=False),
        sa.CheckConstraint("quantidade > 0", name="vendas_quantidade_positiva"),
        schema="erp",
    )
    op.create_index(
        "ix_erp_vendas_sku_data", "vendas", ["sku_id", "data"], schema="erp"
    )

    op.create_table(
        "pedidos_compra",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "fornecedor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("erp.fornecedores.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                *PEDIDO_STATUS,
                name="pedido_compra_status",
                schema="erp",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "criado_em",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("aprovado_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("enviado_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("recebido_em", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("data_prevista_entrega", sa.Date, nullable=True),
        sa.Column("valor_total_reais", sa.Integer, nullable=False),
        sa.Column("observacao", sa.Text, nullable=True),
        schema="erp",
    )

    op.create_table(
        "pedidos_compra_itens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "pedido_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("erp.pedidos_compra.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sku_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("erp.skus.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantidade", sa.Integer, nullable=False),
        sa.Column("preco_unitario_reais", sa.Integer, nullable=False),
        sa.Column(
            "quantidade_recebida",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.CheckConstraint(
            "quantidade > 0", name="pedidos_compra_itens_quantidade_positiva"
        ),
        schema="erp",
    )
    op.create_index(
        "ix_erp_pedidos_itens_pedido",
        "pedidos_compra_itens",
        ["pedido_id"],
        schema="erp",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_erp_pedidos_itens_pedido", table_name="pedidos_compra_itens", schema="erp"
    )
    op.drop_table("pedidos_compra_itens", schema="erp")
    op.drop_table("pedidos_compra", schema="erp")
    op.drop_index("ix_erp_vendas_sku_data", table_name="vendas", schema="erp")
    op.drop_table("vendas", schema="erp")
    op.drop_index(
        "ix_erp_movimentacoes_sku_data",
        table_name="movimentacoes_estoque",
        schema="erp",
    )
    op.drop_table("movimentacoes_estoque", schema="erp")
    op.drop_table("estoque_snapshot", schema="erp")
    op.drop_table("fornecedores_skus", schema="erp")
    op.drop_table("fornecedores", schema="erp")
    op.drop_index("ix_erp_skus_produto_id", table_name="skus", schema="erp")
    op.drop_table("skus", schema="erp")
    op.drop_table("produtos", schema="erp")

    op.execute("DROP TYPE IF EXISTS erp.pedido_compra_status")
    op.execute("DROP TYPE IF EXISTS erp.movimentacao_tipo")
