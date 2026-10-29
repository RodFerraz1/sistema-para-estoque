"""Barcode of the SKU: `ean` in `erp.skus`.

The sales team scans the barcode (EAN-13) on the label to find the SKU. Nullable because
not every SKU in a real ERP has one, unique because one barcode names one SKU.

Revision ID: 0025_ean_do_sku
Revises: 0024_piso_gondola
Create Date: 2026-10-18

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025_ean_do_sku"
down_revision: Union[str, Sequence[str], None] = "0024_piso_gondola"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("skus", sa.Column("ean", sa.Text, nullable=True, unique=True), schema="erp")


def downgrade() -> None:
    op.drop_column("skus", "ean", schema="erp")
