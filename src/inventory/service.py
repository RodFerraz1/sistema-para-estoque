"""Módulo `inventory`: sabe sobre estoque atual e cobertura.

`cobertura_meses` depende de giro, portanto injeta `Sales`. Essa é
dependência intra-módulo explícita (documentada em module-interfaces.md).
"""
from __future__ import annotations

from uuid import UUID

from src.erp_adapter.port import ERPAdapter
from src.inventory.schemas import Cobertura, Estoque
from src.sales.service import Sales


class Inventory:
    def __init__(self, erp: ERPAdapter, sales: Sales) -> None:
        self._erp = erp
        self._sales = sales

    def estoque_atual(self, sku_id: UUID) -> Estoque | None:
        raw = self._erp.get_estoque_atual(sku_id)
        if raw is None:
            return None
        return Estoque(
            quantidade_disponivel=raw.quantidade_disponivel,
            quantidade_reservada=raw.quantidade_reservada,
            atualizado_em=raw.atualizado_em,
        )

    def cobertura_meses(self, sku_id: UUID) -> Cobertura:
        estoque = self.estoque_atual(sku_id)
        giro = self._sales.giro_medio_mensal(sku_id)
        if giro.unidades_por_mes == 0.0:
            return Cobertura(meses=None, sem_giro=True)
        disponivel = estoque.quantidade_disponivel if estoque is not None else 0
        return Cobertura(
            meses=disponivel / giro.unidades_por_mes,
            sem_giro=False,
        )
