"""DTOs crus retornados pelo `erp_adapter`.

Refletem o schema `erp` sem transformação. Módulos superiores (`catalog`,
`inventory`, `sales`) convertem esses tipos em conceitos de domínio.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class _RawBase(BaseModel):
    model_config = ConfigDict(frozen=True)


class SKURaw(_RawBase):
    id: UUID
    produto_id: UUID
    sku_code: str
    cor: str
    tamanho: str
    gramatura: int | None
    material: str | None
    ativo: bool
    produto_nome: str
    produto_categoria: str


class FiltrosSKU(BaseModel):
    categoria: str | None = None
    ativo: bool | None = True


class FornecedorRaw(_RawBase):
    id: UUID
    nome: str
    cnpj: str
    prazo_pagamento_padrao: str
    pedido_minimo_reais: int
    lead_time_dias_contratado: int
    ativo: bool


class FornecedorSKURaw(_RawBase):
    fornecedor_id: UUID
    sku_id: UUID
    fornecedor_nome: str
    preco_unitario_atual: int
    moq_unidades: int
    lead_time_dias_contratado: int
    lead_time_dias_observado: int | None
    prazo_pagamento_padrao: str
    pedido_minimo_reais: int
    ativo: bool


class EstoqueRaw(_RawBase):
    sku_id: UUID
    quantidade_disponivel: int
    quantidade_reservada: int
    atualizado_em: datetime


class MovimentacaoRaw(_RawBase):
    id: UUID
    sku_id: UUID
    tipo: str
    quantidade: int
    data: datetime
    referencia_tipo: str | None
    referencia_id: UUID | None
    observacao: str | None


class VendaRaw(_RawBase):
    id: UUID
    sku_id: UUID
    quantidade: int
    valor_unitario_reais: int
    data: datetime
    cliente_ref: str
