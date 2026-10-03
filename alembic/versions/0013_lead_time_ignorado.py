"""Lead time out of the default calculation; rupture by coverage in days (ADR-0006).

Allow `ignorar` in `lead_time_base`. The default version (v1, while it still has the
previous default values) moves to the new default: `lead_time_base = ignorar` and only
`abaixo_do_piso_alerta` as alert reason. Versions saved by the buyer don't change.

The downgrade turns the default back and, since the old constraint doesn't know
`ignorar`, moves any other version saved with it to `observado`, the previous default.

Revision ID: 0013_lead_time_ignorado
Revises: 0012_sku_em_contexto
Create Date: 2026-10-03

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0013_lead_time_ignorado"
down_revision: Union[str, Sequence[str], None] = "0012_sku_em_contexto"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT = "politicas_compra_lead_time_base_check"
_BASES_ANTIGAS = ("observado", "contratado", "maior")
_BASES_NOVAS = ("ignorar", *_BASES_ANTIGAS)
_MOTIVOS_ANTIGOS = ("ruptura_antes_da_chegada", "abaixo_do_piso_alerta")
_MOTIVOS_NOVOS = ("abaixo_do_piso_alerta",)


def _in(coluna: str, valores: tuple[str, ...]) -> str:
    return f"{coluna} IN (" + ", ".join(f"'{v}'" for v in valores) + ")"


def _array(valores: tuple[str, ...]) -> str:
    return "ARRAY[" + ", ".join(f"'{v}'" for v in valores) + "]::text[]"


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "politicas_compra", schema="copilot")
    op.create_check_constraint(
        _CONSTRAINT, "politicas_compra", _in("lead_time_base", _BASES_NOVAS), schema="copilot"
    )
    op.execute(
        f"""
        UPDATE copilot.politicas_compra
        SET lead_time_base = 'ignorar', motivos_de_alerta = {_array(_MOTIVOS_NOVOS)}
        WHERE versao = 1 AND lead_time_base = 'observado'
          AND motivos_de_alerta = {_array(_MOTIVOS_ANTIGOS)}
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE copilot.politicas_compra
        SET lead_time_base = 'observado', motivos_de_alerta = {_array(_MOTIVOS_ANTIGOS)}
        WHERE versao = 1 AND lead_time_base = 'ignorar' AND motivos_de_alerta = {_array(_MOTIVOS_NOVOS)}
        """
    )
    op.execute("UPDATE copilot.politicas_compra SET lead_time_base = 'observado' WHERE lead_time_base = 'ignorar'")
    op.drop_constraint(_CONSTRAINT, "politicas_compra", schema="copilot")
    op.create_check_constraint(
        _CONSTRAINT, "politicas_compra", _in("lead_time_base", _BASES_ANTIGAS), schema="copilot"
    )
