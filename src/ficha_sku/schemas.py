"""DTOs de domínio do módulo `ficha_sku`."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.catalog.schemas import SKU, FornecedorParaSKU
from src.inventory.schemas import Cobertura, Estoque
from src.sales.schemas import GiroMedioMensal


class Ficha(BaseModel):
    """Estado atual de um SKU pronto pra decisão de compra."""

    model_config = ConfigDict(frozen=True)

    sku: SKU
    estoque: Estoque
    giro: GiroMedioMensal
    cobertura: Cobertura
    fornecedores: list[FornecedorParaSKU]
