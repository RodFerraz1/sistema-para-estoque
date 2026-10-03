"""Módulo `ficha_sku`: compõe a ficha de um SKU a partir de catálogo,
estoque e vendas.

Só lê dos módulos de domínio; não fala com o `ERPAdapter` diretamente.
"""
from __future__ import annotations

from src.catalog.service import Catalog
from src.ficha_sku.schemas import Ficha
from src.inventory.service import Inventory
from src.sales.service import Sales


class SKUSemEstoque(Exception):
    def __init__(self, sku_code: str) -> None:
        super().__init__(f"SKU '{sku_code}' sem snapshot de estoque")
        self.sku_code = sku_code


class FichaSKU:
    def __init__(self, catalog: Catalog, inventory: Inventory, sales: Sales) -> None:
        self._catalog = catalog
        self._inventory = inventory
        self._sales = sales

    def completa(self, sku_code: str) -> Ficha | None:
        sku = self._catalog.carregar_sku(sku_code)
        if sku is None:
            return None
        estoque = self._inventory.estoque_atual(sku_code)
        if estoque is None:
            raise SKUSemEstoque(sku_code)
        return Ficha(
            sku=sku,
            estoque=estoque,
            em_transito=self._inventory.em_transito(sku_code).total_unidades,
            giro=self._sales.giro_medio_mensal(sku_code),
            cobertura=self._inventory.cobertura_meses(sku_code),
            fornecedores=self._catalog.fornecedores_de(sku_code),
        )
