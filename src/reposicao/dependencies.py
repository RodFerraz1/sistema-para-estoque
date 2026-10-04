from __future__ import annotations

from fastapi import Depends

from src.catalog.dependencies import get_catalog
from src.catalog.service import Catalog
from src.inventory.dependencies import get_inventory
from src.inventory.service import Inventory
from src.politica_compra.dependencies import get_politica_compra_repositorio
from src.politica_compra.repositorio import PoliticaCompraRepositorio
from src.reposicao.service import Relogio, Reposicao, agora_utc
from src.sales.dependencies import get_sales
from src.sales.service import Sales


def get_relogio() -> Relogio:
    """Em testes, sobrescreva para controlar o dia de hoje da queda de venda."""
    return agora_utc


def get_reposicao(
    catalog: Catalog = Depends(get_catalog),
    inventory: Inventory = Depends(get_inventory),
    sales: Sales = Depends(get_sales),
    politicas: PoliticaCompraRepositorio = Depends(get_politica_compra_repositorio),
    relogio: Relogio = Depends(get_relogio),
) -> Reposicao:
    return Reposicao(catalog, inventory, sales, politicas, relogio=relogio)
