"""Pieces the salesperson asks for: `pecas` in `copilot.avisos_gondola`.

The empty-shelf notice carries how many pieces to bring from the warehouse: the shelf mix
suggestion, adjusted by the salesperson. Nullable for old notices and for products without
a shelf capacity, where there is no suggestion and she may leave it blank.

Revision ID: 0026_pecas_do_aviso_gondola
Revises: 0025_ean_do_sku
Create Date: 2026-10-18

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026_pecas_do_aviso_gondola"
down_revision: Union[str, Sequence[str], None] = "0025_ean_do_sku"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("avisos_gondola", sa.Column("pecas", sa.Integer, nullable=True), schema="copilot")


def downgrade() -> None:
    op.drop_column("avisos_gondola", "pecas", schema="copilot")
