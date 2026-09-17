"""DTOs de domínio do módulo `sales`."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class GiroMedioMensal(BaseModel):
    model_config = ConfigDict(frozen=True)

    unidades_por_mes: float
    meses_considerados: int
    total_unidades: int
