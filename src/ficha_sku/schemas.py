"""DTOs de domínio do módulo `ficha_sku`."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.catalog.schemas import SKU, FornecedorParaSKU
from src.inventory.schemas import Cobertura, Estoque
from src.sales.schemas import GiroMedioMensal


class Ficha(BaseModel):
    """Estado atual de um SKU pronto pra decisão de compra. `em_transito` soma as
    unidades ainda por chegar dos pedidos de compra abertos. `primeira_venda` é nula para
    SKU que nunca vendeu."""

    model_config = ConfigDict(frozen=True)

    sku: SKU
    estoque: Estoque
    em_transito: int
    giro: GiroMedioMensal
    cobertura: Cobertura
    fornecedores: list[FornecedorParaSKU]
    primeira_venda: datetime | None


class Retrato(BaseModel):
    """Fichas de vários SKUs lidas de uma vez: o estoque inteiro, no painel, ou um SKU só.
    `skus` vem por `sku_code`; um SKU sem a linha de estoque no ERP fica sem ficha."""

    model_config = ConfigDict(frozen=True)

    skus: list[SKU]
    fichas: dict[str, Ficha]
