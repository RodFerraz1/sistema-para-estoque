"""Add the SKU in context (the screen the chat was asked from) to copilot.registros_decisao.

Revision ID: 0012_sku_em_contexto
Revises: 0011_decisoes_compra
Create Date: 2026-10-01

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_sku_em_contexto"
down_revision: Union[str, Sequence[str], None] = "0011_decisoes_compra"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("registros_decisao", sa.Column("sku_em_contexto", sa.Text, nullable=True), schema="copilot")


def downgrade() -> None:
    op.drop_column("registros_decisao", "sku_em_contexto", schema="copilot")
