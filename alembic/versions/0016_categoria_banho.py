"""Allow the `banho` category in erp.produtos.

The seed's demo story has a bath mat (Tapete Banheiro) in its own category. The
downgrade puts the old constraint back as NOT VALID, so it does not fail on products
already saved as `banho`; the next seed recreates the ERP data without them.

Revision ID: 0016_categoria_banho
Revises: 0015_autoria
Create Date: 2026-10-03

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0016_categoria_banho"
down_revision: Union[str, Sequence[str], None] = "0015_autoria"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT = "produtos_categoria_check"
_CATEGORIAS_ANTIGAS = ("felpudo", "jogo_cama", "mesa", "cozinha")
_CATEGORIAS_NOVAS = (*_CATEGORIAS_ANTIGAS, "banho")


def _trocar(categorias: tuple[str, ...], validar: bool) -> None:
    lista = ", ".join(f"'{c}'" for c in categorias)
    op.drop_constraint(_CONSTRAINT, "produtos", schema="erp", type_="check")
    op.execute(
        f"ALTER TABLE erp.produtos ADD CONSTRAINT {_CONSTRAINT} CHECK (categoria IN ({lista}))"
        + ("" if validar else " NOT VALID")
    )


def upgrade() -> None:
    _trocar(_CATEGORIAS_NOVAS, validar=True)


def downgrade() -> None:
    _trocar(_CATEGORIAS_ANTIGAS, validar=False)
