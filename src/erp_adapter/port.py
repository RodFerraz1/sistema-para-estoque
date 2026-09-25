"""Port abstrato do ERP. Uma implementação (`PostgresERPAdapter`) fala com
Postgres via SQLAlchemy; outra (`InMemoryERPAdapter`) serve para testes de
módulos superiores.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.catalog.schemas import SKU, Fornecedor, FornecedorParaSKU
from src.inventory.schemas import Estoque, Movimentacao
from src.sales.schemas import Venda


class ERPAdapter(Protocol):
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
