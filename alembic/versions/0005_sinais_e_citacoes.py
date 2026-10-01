"""Add sinais and citacoes to copilot.registros_decisao.

Revision ID: 0005_sinais_e_citacoes
Revises: 0004_registros_decisao
Create Date: 2026-09-30

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_sinais_e_citacoes"
down_revision: Union[str, Sequence[str], None] = "0004_registros_decisao"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for coluna in ("sinais", "citacoes"):
        op.add_column(
            "registros_decisao",
            sa.Column(coluna, postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
            schema="copilot",
        )


def downgrade() -> None:
    for coluna in ("citacoes", "sinais"):
        op.drop_column("registros_decisao", coluna, schema="copilot")
