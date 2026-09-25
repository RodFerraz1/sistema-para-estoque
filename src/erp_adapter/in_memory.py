"""Implementação em memória do `ERPAdapter`, apenas para testes.

Aceita listas planas de raws e serve leituras filtradas. Não valida
consistência entre coleções: é responsabilidade do teste montar dados
coerentes.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from src.catalog.schemas import SKU, Fornecedor, FornecedorParaSKU
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
from src.inventory.schemas import Estoque, Movimentacao
from src.sales.schemas import Venda


def _raw_to_sku(raw: SKURaw) -> SKU:
    return SKU(
        id=raw.id,
        produto_id=raw.produto_id,
        sku_code=raw.sku_code,
        produto_nome=raw.produto_nome,
        categoria=raw.produto_categoria,
        cor=raw.cor,
        tamanho=raw.tamanho,
        gramatura=raw.gramatura,
        material=raw.material,
        ativo=raw.ativo,
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

    def _sku_id(self, sku_code: str) -> UUID | None:
        return next((s.id for s in self.skus if s.sku_code == sku_code), None)

    def carregar_sku(self, sku_code: str) -> SKU | None:
        return next(
            (_raw_to_sku(s) for s in self.skus if s.sku_code == sku_code), None
        )

    def listar_skus(self) -> list[SKU]:
        ativos = (s for s in self.skus if s.ativo)
        return [_raw_to_sku(s) for s in sorted(ativos, key=lambda s: s.sku_code)]

    def carregar_fornecedor(self, fornecedor_id: UUID) -> Fornecedor | None:
        raw = next((f for f in self.fornecedores if f.id == fornecedor_id), None)
        if raw is None:
            return None
        return Fornecedor(
            id=raw.id,
            nome=raw.nome,
            cnpj=raw.cnpj,
            prazo_pagamento_padrao=raw.prazo_pagamento_padrao,
            pedido_minimo_reais=raw.pedido_minimo_reais,
            lead_time_dias_contratado=raw.lead_time_dias_contratado,
            ativo=raw.ativo,
        )

    def fornecedores_de(self, sku_code: str) -> list[FornecedorParaSKU]:
        sku_id = self._sku_id(sku_code)
        ativos_ids = {f.id for f in self.fornecedores if f.ativo}
        vinculos = sorted(
            (
                fs
                for fs in self.fornecedores_skus
                if fs.sku_id == sku_id and fs.ativo and fs.fornecedor_id in ativos_ids
            ),
            key=lambda fs: fs.preco_unitario_atual,
        )
        return [
            FornecedorParaSKU(
                fornecedor_id=fs.fornecedor_id,
                fornecedor_nome=fs.fornecedor_nome,
                preco_unitario_reais=fs.preco_unitario_atual,
                moq_unidades=fs.moq_unidades,
                lead_time_dias_contratado=fs.lead_time_dias_contratado,
                lead_time_dias_observado=fs.lead_time_dias_observado,
                prazo_pagamento_padrao=fs.prazo_pagamento_padrao,
                pedido_minimo_reais=fs.pedido_minimo_reais,
            )
            for fs in vinculos
        ]

    def estoque_de(self, sku_code: str) -> Estoque | None:
        sku_id = self._sku_id(sku_code)
        raw = next((e for e in self.estoques if e.sku_id == sku_id), None)
        if raw is None:
            return None
        return Estoque(
            quantidade_disponivel=raw.quantidade_disponivel,
            quantidade_reservada=raw.quantidade_reservada,
            atualizado_em=raw.atualizado_em,
        )

    def vendas_de(self, sku_code: str, desde: datetime) -> list[Venda]:
        sku_id = self._sku_id(sku_code)
        vendas = sorted(
            (v for v in self.vendas if v.sku_id == sku_id and v.data >= desde),
            key=lambda v: v.data,
        )
        return [
            Venda(
                id=v.id,
                sku_id=v.sku_id,
                quantidade=v.quantidade,
                valor_unitario_reais=v.valor_unitario_reais,
                data=v.data,
                cliente_ref=v.cliente_ref,
            )
            for v in vendas
        ]

    def movimentacoes_de(
        self, sku_code: str, desde: datetime
    ) -> list[Movimentacao]:
        sku_id = self._sku_id(sku_code)
        movs = sorted(
            (m for m in self.movimentacoes if m.sku_id == sku_id and m.data >= desde),
            key=lambda m: m.data,
        )
        return [
            Movimentacao(
                id=m.id,
                sku_id=m.sku_id,
                tipo=m.tipo,
                quantidade=m.quantidade,
                data=m.data,
                referencia_tipo=m.referencia_tipo,
                referencia_id=m.referencia_id,
                observacao=m.observacao,
            )
            for m in movs
        ]
