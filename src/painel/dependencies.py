from __future__ import annotations

from fastapi import Depends

from src.catalog.dependencies import get_catalog
from src.catalog.service import Catalog
from src.db.engine import get_engine
from src.ficha_sku.dependencies import get_ficha_sku
from src.ficha_sku.service import FichaSKU
from src.painel.postgres import PostgresAvisosRepositorio, PostgresDecisoesRepositorio
from src.painel.repositorio import AvisosRepositorio, DecisoesRepositorio
from src.painel.service import Painel, Relogio, agora_utc
from src.politica_compra.dependencies import get_politica_compra_repositorio
from src.politica_compra.repositorio import PoliticaCompraRepositorio
from src.purchasing.dependencies import get_purchasing
from src.purchasing.service import Purchasing


def get_avisos_repositorio() -> AvisosRepositorio:
    return PostgresAvisosRepositorio(get_engine())


def get_decisoes_repositorio() -> DecisoesRepositorio:
    return PostgresDecisoesRepositorio(get_engine())


def get_relogio() -> Relogio:
    """Em testes, sobrescreva para controlar a hora dos avisos e das decisões."""
    return agora_utc


def get_painel(
    catalog: Catalog = Depends(get_catalog),
    ficha_sku: FichaSKU = Depends(get_ficha_sku),
    purchasing: Purchasing = Depends(get_purchasing),
    politicas: PoliticaCompraRepositorio = Depends(get_politica_compra_repositorio),
    avisos: AvisosRepositorio = Depends(get_avisos_repositorio),
    decisoes: DecisoesRepositorio = Depends(get_decisoes_repositorio),
    relogio: Relogio = Depends(get_relogio),
) -> Painel:
    return Painel(catalog, ficha_sku, purchasing, politicas, avisos, decisoes, relogio=relogio)
