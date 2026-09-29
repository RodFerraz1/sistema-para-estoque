"""DTOs de domínio do módulo `ai`."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class Trecho(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    documento: str
    titulo: str
    tipo: str
    data: date
    tags: list[str]
    texto: str
