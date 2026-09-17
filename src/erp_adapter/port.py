"""Port abstrato do ERP. Uma implementação (`PostgresERPAdapter`) fala com
Postgres via SQLAlchemy; outra (`InMemoryERPAdapter`) serve para testes de
módulos superiores.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.erp_adapter.schemas import (
    EstoqueRaw,
    FiltrosSKU,
    FornecedorRaw,
    FornecedorSKURaw,
    MovimentacaoRaw,
    SKURaw,
    VendaRaw,
)


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
