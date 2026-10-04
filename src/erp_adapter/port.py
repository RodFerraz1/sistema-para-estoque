"""Port abstrato do ERP. Uma implementação (`PostgresERPAdapter`) fala com
Postgres via SQLAlchemy; outra (`InMemoryERPAdapter`) serve para testes de
módulos superiores.

As leituras em lote (`estoques`, `giros`, `vendas_diarias`, `fornecedores_por_sku`,
`itens_em_transito`) são o retrato do estoque inteiro: uma consulta cada, só dos SKUs
ativos, indexadas por `sku_code`. Um SKU sem nada a devolver fica fora do dicionário.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.catalog.schemas import SKU, Fornecedor, FornecedorParaSKU
from src.erp_adapter.schemas import ItemDePedido
from src.inventory.schemas import EntregaRecebida, Estoque, ItemEmTransito, Movimentacao
from src.sales.schemas import Venda, VendasDoDia, VendasDoMes


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

    def itens_de_pedido_de(self, sku_code: str) -> list[ItemDePedido]:
        """Itens de pedido de compra do SKU, de todos os status, do pedido mais recente
        para o mais antigo."""
        ...

    def entregas_recebidas_de(self, fornecedor_id: UUID) -> list[EntregaRecebida]:
        """Pedidos `recebido_total` do fornecedor com data prevista e data de recebimento,
        do recebido mais recente para o mais antigo."""
        ...

    def estoques(self) -> dict[str, Estoque]: ...

    def giros(self, desde: datetime) -> dict[str, list[VendasDoMes]]:
        """Vendas com `data >= desde` somadas por mês, do mais antigo ao mais recente."""
        ...

    def vendas_diarias(self, desde: datetime) -> dict[str, list[VendasDoDia]]:
        """Vendas com `data >= desde` somadas por dia, do mais antigo ao mais recente."""
        ...

    def fornecedores_por_sku(self) -> dict[str, list[FornecedorParaSKU]]:
        """Na regra e na ordem de `fornecedores_de`."""
        ...

    def itens_em_transito(self) -> dict[str, list[ItemEmTransito]]:
        """Na regra e na ordem de `itens_em_transito_de`."""
        ...
