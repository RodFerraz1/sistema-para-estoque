"""Módulo `ficha_sku`: compõe a ficha de um SKU a partir de catálogo,
estoque e vendas, um SKU por vez ou o estoque inteiro num retrato.

Só lê dos módulos de domínio; não fala com o `ERPAdapter` diretamente.
"""
from __future__ import annotations

from src.catalog.schemas import SKU, FornecedorParaSKU
from src.catalog.service import Catalog
from src.ficha_sku.schemas import Ficha, Retrato
from src.inventory.schemas import Estoque
from src.inventory.service import Inventory, cobertura
from src.sales.schemas import VendasDoMes
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
        return self._ficha(
            sku,
            estoque,
            em_transito=self._inventory.em_transito(sku_code).total_unidades,
            vendas_por_mes=self._sales.vendas_por_mes(sku_code),
            fornecedores=self._catalog.fornecedores_de(sku_code),
        )

    def retrato_de(self, sku_code: str) -> Retrato | None:
        """O retrato de um SKU só, com as leituras por SKU. `None` para SKU inexistente.
        Propaga `SKUSemEstoque`."""
        ficha = self.completa(sku_code)
        if ficha is None:
            return None
        return Retrato(skus=[ficha.sku], fichas={sku_code: ficha})

    def retrato(self) -> Retrato:
        """As fichas de todos os SKUs ativos, com um número fixo de leituras em lote."""
        skus = self._catalog.listar_skus()
        estoques = self._inventory.estoques()
        em_transito = self._inventory.em_transito_por_sku()
        vendas = self._sales.vendas_por_mes_de_todos()
        fornecedores = self._catalog.fornecedores_por_sku()
        fichas = {
            sku.sku_code: self._ficha(
                sku,
                estoque,
                em_transito=transito.total_unidades if (transito := em_transito.get(sku.sku_code)) else 0,
                vendas_por_mes=vendas.get(sku.sku_code, []),
                fornecedores=fornecedores.get(sku.sku_code, []),
            )
            for sku in skus
            if (estoque := estoques.get(sku.sku_code)) is not None
        }
        return Retrato(skus=skus, fichas=fichas)

    def _ficha(
        self,
        sku: SKU,
        estoque: Estoque,
        *,
        em_transito: int,
        vendas_por_mes: list[VendasDoMes],
        fornecedores: list[FornecedorParaSKU],
    ) -> Ficha:
        giro = self._sales.giro(vendas_por_mes)
        return Ficha(
            sku=sku,
            estoque=estoque,
            em_transito=em_transito,
            giro=giro,
            cobertura=cobertura(estoque.quantidade_disponivel, giro),
            fornecedores=fornecedores,
            primeira_venda=vendas_por_mes[0].primeira_venda if vendas_por_mes else None,
        )
