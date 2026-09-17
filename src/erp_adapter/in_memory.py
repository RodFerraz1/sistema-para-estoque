"""Implementação em memória do `ERPAdapter`, apenas para testes.

Aceita listas planas de raws e serve leituras filtradas. Não valida
consistência entre coleções: é responsabilidade do teste montar dados
coerentes.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from src.erp_adapter.port import ERPAdapter
from src.erp_adapter.schemas import (
    EstoqueRaw,
    FiltrosSKU,
    FornecedorRaw,
    FornecedorSKURaw,
    MovimentacaoRaw,
    SKURaw,
    VendaRaw,
)


class InMemoryERPAdapter(ERPAdapter):
    def __init__(
        self,
        *,
        skus: list[SKURaw] | None = None,
        fornecedores: list[FornecedorRaw] | None = None,
        fornecedores_skus: list[FornecedorSKURaw] | None = None,
        estoques: list[EstoqueRaw] | None = None,
        movimentacoes: list[MovimentacaoRaw] | None = None,
        vendas: list[VendaRaw] | None = None,
    ) -> None:
        self.skus: list[SKURaw] = list(skus or [])
        self.fornecedores: list[FornecedorRaw] = list(fornecedores or [])
        self.fornecedores_skus: list[FornecedorSKURaw] = list(fornecedores_skus or [])
        self.estoques: list[EstoqueRaw] = list(estoques or [])
        self.movimentacoes: list[MovimentacaoRaw] = list(movimentacoes or [])
        self.vendas: list[VendaRaw] = list(vendas or [])

    def get_sku_raw(self, sku_id: UUID) -> SKURaw | None:
        return next((s for s in self.skus if s.id == sku_id), None)

    def get_sku_raw_por_codigo(self, sku_code: str) -> SKURaw | None:
        return next((s for s in self.skus if s.sku_code == sku_code), None)

    def list_skus_raw(self, filtros: FiltrosSKU) -> list[SKURaw]:
        result = self.skus
        if filtros.categoria is not None:
            result = [s for s in result if s.produto_categoria == filtros.categoria]
        if filtros.ativo is not None:
            result = [s for s in result if s.ativo == filtros.ativo]
        return sorted(result, key=lambda s: s.sku_code)

    def get_fornecedor_raw(self, fornecedor_id: UUID) -> FornecedorRaw | None:
        return next((f for f in self.fornecedores if f.id == fornecedor_id), None)

    def list_fornecedores_para_sku(self, sku_id: UUID) -> list[FornecedorSKURaw]:
        ativos_ids = {f.id for f in self.fornecedores if f.ativo}
        result = [
            fs
            for fs in self.fornecedores_skus
            if fs.sku_id == sku_id and fs.ativo and fs.fornecedor_id in ativos_ids
        ]
        return sorted(result, key=lambda r: r.preco_unitario_atual)

    def get_estoque_atual(self, sku_id: UUID) -> EstoqueRaw | None:
        return next((e for e in self.estoques if e.sku_id == sku_id), None)

    def list_movimentacoes(
        self, sku_id: UUID, desde: datetime
    ) -> list[MovimentacaoRaw]:
        return sorted(
            (m for m in self.movimentacoes if m.sku_id == sku_id and m.data >= desde),
            key=lambda m: m.data,
        )

    def list_vendas(self, sku_id: UUID, desde: datetime) -> list[VendaRaw]:
        return sorted(
            (v for v in self.vendas if v.sku_id == sku_id and v.data >= desde),
            key=lambda v: v.data,
        )
