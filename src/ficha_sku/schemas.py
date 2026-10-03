"""DTOs de domínio do módulo `ficha_sku`."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.catalog.schemas import SKU, FornecedorParaSKU
from src.inventory.schemas import Cobertura, Estoque
from src.sales.schemas import GiroMedioMensal


class Ficha(BaseModel):
    """Estado atual de um SKU pronto pra decisão de compra. `em_transito` soma as
    unidades ainda por chegar dos pedidos de compra abertos."""

    model_config = ConfigDict(frozen=True)

    sku: SKU
    estoque: Estoque
    em_transito: int
    giro: GiroMedioMensal
    cobertura: Cobertura
    fornecedores: list[FornecedorParaSKU]
