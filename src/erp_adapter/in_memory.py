"""Implementação em memória do `ERPAdapter`, apenas para testes.

Aceita DTOs de domínio e serve leituras filtradas. `Estoque` e
`FornecedorParaSKU` não carregam o SKU, então chegam indexados por
`sku_code`; vínculo inativo é representado pela ausência na lista. Não
valida consistência entre coleções: é responsabilidade do teste montar
dados coerentes.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from src.catalog.schemas import SKU, Fornecedor, FornecedorParaSKU
from src.erp_adapter.port import ERPAdapter
from src.inventory.schemas import Estoque, Movimentacao
from src.sales.schemas import Venda


class InMemoryERPAdapter(ERPAdapter):
    def __init__(
        self,
        *,
        skus: list[SKU] | None = None,
        fornecedores: list[Fornecedor] | None = None,
        fornecedores_por_sku: dict[str, list[FornecedorParaSKU]] | None = None,
        estoques: dict[str, Estoque] | None = None,
        movimentacoes: list[Movimentacao] | None = None,
        vendas: list[Venda] | None = None,
    ) -> None:
        self.skus: list[SKU] = list(skus or [])
        self.fornecedores: list[Fornecedor] = list(fornecedores or [])
        self.fornecedores_por_sku: dict[str, list[FornecedorParaSKU]] = dict(
            fornecedores_por_sku or {}
        )
        self.estoques: dict[str, Estoque] = dict(estoques or {})
        self.movimentacoes: list[Movimentacao] = list(movimentacoes or [])
        self.vendas: list[Venda] = list(vendas or [])

    def _sku_id(self, sku_code: str) -> UUID | None:
        return next((s.id for s in self.skus if s.sku_code == sku_code), None)

    def carregar_sku(self, sku_code: str) -> SKU | None:
        return next((s for s in self.skus if s.sku_code == sku_code), None)

    def listar_skus(self) -> list[SKU]:
        return sorted((s for s in self.skus if s.ativo), key=lambda s: s.sku_code)

    def carregar_fornecedor(self, fornecedor_id: UUID) -> Fornecedor | None:
        return next((f for f in self.fornecedores if f.id == fornecedor_id), None)

    def fornecedores_de(self, sku_code: str) -> list[FornecedorParaSKU]:
        ativos_ids = {f.id for f in self.fornecedores if f.ativo}
        return sorted(
            (
                f
                for f in self.fornecedores_por_sku.get(sku_code, [])
                if f.fornecedor_id in ativos_ids
            ),
            key=lambda f: f.preco_unitario_reais,
        )

    def estoque_de(self, sku_code: str) -> Estoque | None:
        return self.estoques.get(sku_code)

    def vendas_de(self, sku_code: str, desde: datetime) -> list[Venda]:
        sku_id = self._sku_id(sku_code)
        return sorted(
            (v for v in self.vendas if v.sku_id == sku_id and v.data >= desde),
            key=lambda v: v.data,
        )

    def movimentacoes_de(
        self, sku_code: str, desde: datetime
    ) -> list[Movimentacao]:
        sku_id = self._sku_id(sku_code)
        return sorted(
            (m for m in self.movimentacoes if m.sku_id == sku_id and m.data >= desde),
            key=lambda m: m.data,
        )
