from __future__ import annotations

from fastapi import Depends

from src.catalog.service import Catalog
from src.erp_adapter.dependencies import get_erp_adapter
from src.erp_adapter.port import ERPAdapter


def get_catalog(erp: ERPAdapter = Depends(get_erp_adapter)) -> Catalog:
    return Catalog(erp)
