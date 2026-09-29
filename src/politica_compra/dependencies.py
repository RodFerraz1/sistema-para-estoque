from __future__ import annotations

from src.db.engine import get_engine
from src.politica_compra.postgres import PostgresPoliticaCompraRepositorio
from src.politica_compra.repositorio import PoliticaCompraRepositorio


def get_politica_compra_repositorio() -> PoliticaCompraRepositorio:
    return PostgresPoliticaCompraRepositorio(get_engine())
