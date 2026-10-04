"""copilot.setores, copilot.setores_sku and copilot.avisos_gondola.

Store sections are a simple list kept by the admin (unique name, case-insensitive, and an
active flag). `setores_sku` is the known section of each SKU, written by the last empty-shelf
notice or by the shelf check that corrected it; the ERP has no such data. `usuario_id` is
null for the rows written by the seed.

An empty-shelf notice records the SKU, the section, an optional comment, the ERP available
quantity at that moment, the name of who sent it and the logged-in user. It is open until a
shelf check of the same SKU is registered after it: there is no status column.

Revision ID: 0022_setores_e_avisos_gondola
Revises: 0021_notificacao_para_uma_pessoa
Create Date: 2026-10-04

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022_setores_e_avisos_gondola"
down_revision: Union[str, Sequence[str], None] = "0021_notificacao_para_uma_pessoa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "setores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("nome", sa.Text, nullable=False),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.CheckConstraint("btrim(nome) <> ''", name="setores_nome_check"),
        schema="copilot",
    )
    op.create_index("setores_nome_key", "setores", [sa.text("lower(nome)")], unique=True, schema="copilot")

    op.create_table(
        "setores_sku",
        sa.Column("sku_code", sa.Text, primary_key=True),
        sa.Column("setor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("copilot.setores.id"), nullable=False),
        sa.Column(
            "atualizado_em", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("copilot.usuarios.id"), nullable=True
        ),
        schema="copilot",
    )

    op.create_table(
        "avisos_gondola",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sku_code", sa.Text, nullable=False),
        sa.Column("setor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("copilot.setores.id"), nullable=False),
        sa.Column("comentario", sa.Text, nullable=True),
        sa.Column("disponivel_no_erp", sa.Integer, nullable=False),
        sa.Column("avisado_por", sa.Text, nullable=False),
        sa.Column(
            "usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("copilot.usuarios.id"), nullable=False
        ),
        sa.Column(
            "criado_em", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("btrim(avisado_por) <> ''", name="avisos_gondola_avisado_por_check"),
        schema="copilot",
    )
    op.create_index(
        "avisos_gondola_sku_code_criado_em_idx", "avisos_gondola", ["sku_code", "criado_em"], schema="copilot"
    )
    op.create_index(
        "avisos_gondola_usuario_id_criado_em_idx", "avisos_gondola", ["usuario_id", "criado_em"], schema="copilot"
    )


def downgrade() -> None:
    op.drop_table("avisos_gondola", schema="copilot")
    op.drop_table("setores_sku", schema="copilot")
    op.drop_table("setores", schema="copilot")
