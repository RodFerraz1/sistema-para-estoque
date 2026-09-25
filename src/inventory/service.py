"""Módulo `inventory`: sabe sobre estoque atual e cobertura.

`cobertura_meses` depende de giro, portanto injeta `Sales`. Essa é
dependência intra-módulo explícita (documentada em module-interfaces.md).
"""
from __future__ import annotations

from src.catalog.schemas import SKU
from src.erp_adapter.port import ERPAdapter
from src.inventory.schemas import Cobertura, Estoque, SKUAbaixoDoPiso
from src.sales.service import Sales


class Inventory:
    def __init__(self, erp: ERPAdapter, sales: Sales) -> None:
        self._erp = erp
        self._sales = sales

    def estoque_atual(self, sku_code: str) -> Estoque | None:
        return self._erp.estoque_de(sku_code)

    def cobertura_meses(self, sku_code: str) -> Cobertura:
        sku = self._erp.carregar_sku(sku_code)
        if sku is None:
            return Cobertura(meses=None, sem_giro=True)
        return self._cobertura(sku)

    def _cobertura(self, sku: SKU) -> Cobertura:
        estoque = self.estoque_atual(sku.sku_code)
        giro = self._sales.giro_medio_mensal(sku.id)
        if giro.unidades_por_mes == 0.0:
            return Cobertura(meses=None, sem_giro=True)
        disponivel = estoque.quantidade_disponivel if estoque is not None else 0
        return Cobertura(
            meses=disponivel / giro.unidades_por_mes,
            sem_giro=False,
        )

    def abaixo_do_piso(self, dias_piso: int = 20) -> list[SKUAbaixoDoPiso]:
        """SKUs ativos com cobertura abaixo do piso, ordenados por urgência.

        Converte `dias_piso` em meses via `dias_piso / 30`. SKUs sem giro
        (cobertura indefinida) ficam de fora - sem demanda, não há alerta
        de reposição.
        """
        piso_meses = dias_piso / 30
        alertas: list[SKUAbaixoDoPiso] = []
        for sku in self._erp.listar_skus():
            cobertura = self._cobertura(sku)
            if cobertura.meses is None:
                continue
            if cobertura.meses >= piso_meses:
                continue
            alertas.append(
                SKUAbaixoDoPiso(
                    sku_id=sku.id,
                    sku_code=sku.sku_code,
                    produto_nome=sku.produto_nome,
                    cobertura_meses=cobertura.meses,
                )
            )
        alertas.sort(key=lambda a: a.cobertura_meses)
        return alertas
