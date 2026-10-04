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
from src.reposicao.postgres import (
    PostgresAvisosGondolaRepositorio,
    PostgresCapacidadesGondolaRepositorio,
    PostgresSetoresRepositorio,
    PostgresVerificacoesRepositorio,
)
from src.reposicao.repositorio import (
    AvisosGondolaRepositorio,
    CapacidadesGondolaRepositorio,
    SetoresRepositorio,
    VerificacoesRepositorio,
)
from src.reposicao.service import Relogio, Reposicao, agora_utc
from src.sales.dependencies import get_sales
from src.sales.service import Sales


def get_verificacoes_repositorio() -> VerificacoesRepositorio:
    return PostgresVerificacoesRepositorio(get_engine())


def get_setores_repositorio() -> SetoresRepositorio:
    return PostgresSetoresRepositorio(get_engine())


def get_avisos_gondola_repositorio() -> AvisosGondolaRepositorio:
    return PostgresAvisosGondolaRepositorio(get_engine())


def get_capacidades_gondola_repositorio() -> CapacidadesGondolaRepositorio:
    return PostgresCapacidadesGondolaRepositorio(get_engine())


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
    setores: SetoresRepositorio = Depends(get_setores_repositorio),
    avisos: AvisosGondolaRepositorio = Depends(get_avisos_gondola_repositorio),
    capacidades: CapacidadesGondolaRepositorio = Depends(get_capacidades_gondola_repositorio),
    notificacoes: Notificacoes = Depends(get_notificacoes),
    relogio: Relogio = Depends(get_relogio),
) -> Reposicao:
    return Reposicao(
        catalog, inventory, sales, politicas, verificacoes, setores, avisos, capacidades, notificacoes, relogio=relogio
    )
