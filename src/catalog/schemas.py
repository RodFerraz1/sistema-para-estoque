"""DTOs de domínio do módulo `catalog`."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class _CatalogDTO(BaseModel):
    model_config = ConfigDict(frozen=True)


class SKU(_CatalogDTO):
    id: UUID
    produto_id: UUID
    sku_code: str
    produto_nome: str
    categoria: str
    cor: str
    tamanho: str
    gramatura: int | None
    material: str | None
    ativo: bool


class Fornecedor(_CatalogDTO):
    """Fornecedor do atacadista, independente de qualquer SKU.

    `FornecedorParaSKU` é a visão comercial de um fornecedor *para um SKU
    específico* (preço, MOQ); esta é a entidade em si.
    """

    id: UUID
    nome: str
    cnpj: str
    prazo_pagamento_padrao: str
    pedido_minimo_reais: int
    lead_time_dias_contratado: int
    ativo: bool


class FornecedorParaSKU(_CatalogDTO):
    fornecedor_id: UUID
    fornecedor_nome: str
    preco_unitario_reais: int
    moq_unidades: int
    lead_time_dias_contratado: int
    lead_time_dias_observado: int | None
    prazo_pagamento_padrao: str
    pedido_minimo_reais: int
