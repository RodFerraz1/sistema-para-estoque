"""Módulo `catalog`: sabe sobre SKU, produto e fornecedor.

Não sabe sobre estoque, venda ou pedido. Consome apenas o `ERPAdapter`.
"""
from __future__ import annotations

from uuid import UUID

from src.catalog.schemas import SKU, FornecedorParaSKU
from src.erp_adapter.port import ERPAdapter
from src.erp_adapter.schemas import FornecedorSKURaw, SKURaw


def _to_sku(raw: SKURaw) -> SKU:
    return SKU(
        id=raw.id,
        sku_code=raw.sku_code,
        produto_nome=raw.produto_nome,
        categoria=raw.produto_categoria,
        cor=raw.cor,
        tamanho=raw.tamanho,
        gramatura=raw.gramatura,
        material=raw.material,
        ativo=raw.ativo,
    )


def _to_fornecedor(raw: FornecedorSKURaw) -> FornecedorParaSKU:
    return FornecedorParaSKU(
        fornecedor_id=raw.fornecedor_id,
        fornecedor_nome=raw.fornecedor_nome,
        preco_unitario_reais=raw.preco_unitario_atual,
        moq_unidades=raw.moq_unidades,
        lead_time_dias_contratado=raw.lead_time_dias_contratado,
        lead_time_dias_observado=raw.lead_time_dias_observado,
        prazo_pagamento_padrao=raw.prazo_pagamento_padrao,
        pedido_minimo_reais=raw.pedido_minimo_reais,
    )


class Catalog:
    def __init__(self, erp: ERPAdapter) -> None:
        self._erp = erp

    def get_sku(self, sku_id: UUID) -> SKU | None:
        raw = self._erp.get_sku_raw(sku_id)
        return _to_sku(raw) if raw is not None else None

    def buscar_sku_por_codigo(self, sku_code: str) -> SKU | None:
        raw = self._erp.get_sku_raw_por_codigo(sku_code)
        return _to_sku(raw) if raw is not None else None

    def list_fornecedores_para_sku(self, sku_id: UUID) -> list[FornecedorParaSKU]:
        return [
            _to_fornecedor(raw)
            for raw in self._erp.list_fornecedores_para_sku(sku_id)
        ]
