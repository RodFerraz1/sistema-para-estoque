from __future__ import annotations

from fastapi import Depends

from src.aprovacao.postgres import PostgresSugestoesFilaRepositorio
from src.aprovacao.repositorio import SugestoesFilaRepositorio
from src.aprovacao.service import Aprovacao
from src.catalog.dependencies import get_catalog
from src.catalog.service import Catalog
from src.db.engine import get_engine
from src.purchasing.dependencies import get_purchasing
from src.purchasing.service import Purchasing


def get_sugestoes_fila_repositorio() -> SugestoesFilaRepositorio:
    return PostgresSugestoesFilaRepositorio(get_engine())


def get_aprovacao(
    catalog: Catalog = Depends(get_catalog),
    purchasing: Purchasing = Depends(get_purchasing),
    fila: SugestoesFilaRepositorio = Depends(get_sugestoes_fila_repositorio),
) -> Aprovacao:
    return Aprovacao(catalog, purchasing, fila)
