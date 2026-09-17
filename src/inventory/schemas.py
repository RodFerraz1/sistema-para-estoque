"""DTOs de domínio do módulo `inventory`."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Estoque(BaseModel):
    model_config = ConfigDict(frozen=True)

    quantidade_disponivel: int
    quantidade_reservada: int
    atualizado_em: datetime


class Cobertura(BaseModel):
    """Cobertura em meses.

    `sem_giro=True` sinaliza que o SKU não teve vendas na janela e portanto
    o cálculo `estoque / giro` é indefinido. Nesse caso `meses` é `None`.
    """

    model_config = ConfigDict(frozen=True)

    meses: float | None
    sem_giro: bool


class SKUAbaixoDoPiso(BaseModel):
    """SKU com cobertura abaixo do piso configurado.

    SKUs sem giro (cobertura indefinida) nunca aparecem aqui - sem demanda,
    não há alerta de reposição.
    """

    model_config = ConfigDict(frozen=True)

    sku_id: UUID
    sku_code: str
    produto_nome: str
    cobertura_meses: float
