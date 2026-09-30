"""Port abstrato do ERP. Uma implementação (`PostgresERPAdapter`) fala com
Postgres via SQLAlchemy; outra (`InMemoryERPAdapter`) serve para testes de
módulos superiores.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from src.catalog.schemas import SKU, Fornecedor, FornecedorParaSKU
from src.inventory.schemas import Estoque, ItemEmTransito, Movimentacao
from src.purchasing.schemas import ItemNovoPedido
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

    def itens_em_transito_de(self, sku_code: str) -> list[ItemEmTransito]:
        """Itens de pedidos `aprovado`, `enviado` ou `recebido_parcial` com
        `quantidade - quantidade_recebida > 0`, por data prevista de entrega
        (sem data por último)."""
        ...

    def fornecedor_tem_pedido(self, fornecedor_id: UUID) -> bool:
        """Se há pedido de compra do fornecedor fora de `rascunho` e `cancelado`."""
        ...

    def criar_pedido_compra(
        self,
        fornecedor_id: UUID,
        itens: list[ItemNovoPedido],
        data_prevista_entrega: date,
        observacao: str,
    ) -> UUID:
        """Única escrita do Copilot no ERP: cria o pedido já `aprovado`, com
        `aprovado_em` agora e o valor total somado dos itens, numa transação.
        `ValueError` sem itens, com fornecedor ou SKU inexistente."""
        ...
