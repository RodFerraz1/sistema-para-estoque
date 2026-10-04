from __future__ import annotations

from fastapi import Depends

from src.catalog.dependencies import get_catalog
from src.catalog.service import Catalog
from src.erp_adapter.dependencies import get_erp_adapter
from src.erp_adapter.port import ERPAdapter
from src.ficha_sku.dependencies import get_ficha_sku
from src.ficha_sku.service import FichaSKU
from src.politica_compra.dependencies import get_politica_compra_repositorio
from src.politica_compra.repositorio import PoliticaCompraRepositorio
from src.purchasing.service import Purchasing


def get_purchasing(
    catalog: Catalog = Depends(get_catalog),
    ficha_sku: FichaSKU = Depends(get_ficha_sku),
    politicas: PoliticaCompraRepositorio = Depends(get_politica_compra_repositorio),
    erp: ERPAdapter = Depends(get_erp_adapter),
) -> Purchasing:
    return Purchasing(catalog, ficha_sku, politicas, erp)
