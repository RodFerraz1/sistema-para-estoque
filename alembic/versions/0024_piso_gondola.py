"""Scheduled shelf restock: `piso_gondola_dias` in the purchase policy.

Add `piso_gondola_dias` to every version of `copilot.politicas_compra`, with the default
agreed with the buyer (half a day of sales left on the shelf).

Revision ID: 0024_piso_gondola
Revises: 0023_mix_de_gondola
Create Date: 2026-10-05

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024_piso_gondola"
down_revision: Union[str, Sequence[str], None] = "0023_mix_de_gondola"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "politicas_compra",
        sa.Column("piso_gondola_dias", sa.Float, nullable=False, server_default="0.5"),
        schema="copilot",
    )
    op.alter_column("politicas_compra", "piso_gondola_dias", server_default=None, schema="copilot")


def downgrade() -> None:
    op.drop_column("politicas_compra", "piso_gondola_dias", schema="copilot")
