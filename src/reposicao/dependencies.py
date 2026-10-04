from __future__ import annotations

from fastapi import Depends

from src.catalog.dependencies import get_catalog
from src.catalog.service import Catalog
from src.db.engine import get_engine
from src.inventory.dependencies import get_inventory
from src.inventory.service import Inventory
from src.notificacoes.dependencies import get_notificacoes
from src.notificacoes.service import Notificacoes
from src.politica_compra.dependencies import get_politica_compra_repositorio
from src.politica_compra.repositorio import PoliticaCompraRepositorio
from src.reposicao.postgres import PostgresVerificacoesRepositorio
from src.reposicao.repositorio import VerificacoesRepositorio
from src.reposicao.service import Relogio, Reposicao, agora_utc
from src.sales.dependencies import get_sales
from src.sales.service import Sales


def get_verificacoes_repositorio() -> VerificacoesRepositorio:
    return PostgresVerificacoesRepositorio(get_engine())


def get_relogio() -> Relogio:
    """Em testes, sobrescreva para controlar o dia de hoje da queda de venda e a hora das
    verificações."""
    return agora_utc


def get_reposicao(
    catalog: Catalog = Depends(get_catalog),
    inventory: Inventory = Depends(get_inventory),
    sales: Sales = Depends(get_sales),
    politicas: PoliticaCompraRepositorio = Depends(get_politica_compra_repositorio),
    verificacoes: VerificacoesRepositorio = Depends(get_verificacoes_repositorio),
    notificacoes: Notificacoes = Depends(get_notificacoes),
    relogio: Relogio = Depends(get_relogio),
) -> Reposicao:
    return Reposicao(catalog, inventory, sales, politicas, verificacoes, notificacoes, relogio=relogio)
