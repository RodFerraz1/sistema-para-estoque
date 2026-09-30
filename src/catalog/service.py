"""Módulo `catalog`: sabe sobre SKU, produto e fornecedor.

Não sabe sobre estoque, venda ou pedido. Consome apenas o `ERPAdapter`.
"""
from __future__ import annotations

from src.catalog.schemas import SKU, FornecedorParaSKU
from src.erp_adapter.port import ERPAdapter


class Catalog:
    def __init__(self, erp: ERPAdapter) -> None:
        self._erp = erp

    def carregar_sku(self, sku_code: str) -> SKU | None:
        return self._erp.carregar_sku(sku_code)

    def listar_skus(self) -> list[SKU]:
        """SKUs ativos, ordenados por `sku_code`."""
        return self._erp.listar_skus()

    def fornecedores_de(self, sku_code: str) -> list[FornecedorParaSKU]:
        return self._erp.fornecedores_de(sku_code)
