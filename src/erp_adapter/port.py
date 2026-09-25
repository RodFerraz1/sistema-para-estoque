"""Port abstrato do ERP. Uma implementação (`PostgresERPAdapter`) fala com
Postgres via SQLAlchemy; outra (`InMemoryERPAdapter`) serve para testes de
módulos superiores.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.catalog.schemas import SKU, Fornecedor, FornecedorParaSKU
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


class ERPAdapter(Protocol):
    def get_sku_raw(self, sku_id: UUID) -> SKURaw | None: ...

    def get_sku_raw_por_codigo(self, sku_code: str) -> SKURaw | None: ...

    def list_skus_raw(self, filtros: FiltrosSKU) -> list[SKURaw]: ...

    def get_fornecedor_raw(self, fornecedor_id: UUID) -> FornecedorRaw | None: ...

    def list_fornecedores_para_sku(self, sku_id: UUID) -> list[FornecedorSKURaw]: ...

    def get_estoque_atual(self, sku_id: UUID) -> EstoqueRaw | None: ...

    def list_movimentacoes(
        self, sku_id: UUID, desde: datetime
    ) -> list[MovimentacaoRaw]: ...

    def list_vendas(self, sku_id: UUID, desde: datetime) -> list[VendaRaw]: ...

    def carregar_sku(self, sku_code: str) -> SKU | None: ...

    def listar_skus(self) -> list[SKU]:
        """SKUs ativos, ordenados por `sku_code`."""
        ...

    def carregar_fornecedor(self, fornecedor_id: UUID) -> Fornecedor | None: ...

    def fornecedores_de(self, sku_code: str) -> list[FornecedorParaSKU]:
        """Só fornecedores ativos com vínculo ativo, do mais barato ao mais caro."""
        ...

    def estoque_de(self, sku_code: str) -> Estoque | None: ...

    def vendas_de(self, sku_code: str, desde: datetime) -> list[Venda]:
        """Vendas com `data >= desde`, em ordem cronológica."""
        ...

    def movimentacoes_de(
        self, sku_code: str, desde: datetime
    ) -> list[Movimentacao]:
        """Movimentações com `data >= desde`, em ordem cronológica."""
        ...
