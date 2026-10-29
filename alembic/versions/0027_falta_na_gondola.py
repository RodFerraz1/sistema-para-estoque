"""Shelf shortage notice from the restocker: `faltou_na_gondola` in `copilot.avisos`.

When the warehouse has fewer pieces than the shelf needs, the restocker restocks what he can
and asks the buyer for the rest. The notice reuses `copilot.avisos`, with the new type and
`quantidade`, the pieces missing. Nullable: the sales notices have no quantity.

Revision ID: 0027_falta_na_gondola
Revises: 0026_pecas_do_aviso_gondola
Create Date: 2026-10-18

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027_falta_na_gondola"
down_revision: Union[str, Sequence[str], None] = "0026_pecas_do_aviso_gondola"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("avisos_tipo_check", "avisos", schema="copilot")
    op.create_check_constraint(
        "avisos_tipo_check", "avisos", "tipo IN ('acabou', 'vendendo_muito', 'faltou_na_gondola')", schema="copilot"
    )
    op.add_column("avisos", sa.Column("quantidade", sa.Integer, nullable=True), schema="copilot")


def downgrade() -> None:
    op.execute("DELETE FROM copilot.avisos WHERE tipo = 'faltou_na_gondola'")
    op.drop_column("avisos", "quantidade", schema="copilot")
    op.drop_constraint("avisos_tipo_check", "avisos", schema="copilot")
    op.create_check_constraint("avisos_tipo_check", "avisos", "tipo IN ('acabou', 'vendendo_muito')", schema="copilot")
