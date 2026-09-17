from __future__ import annotations

from fastapi import Depends

from src.erp_adapter.dependencies import get_erp_adapter
from src.erp_adapter.port import ERPAdapter
from src.sales.service import Sales


def get_sales(erp: ERPAdapter = Depends(get_erp_adapter)) -> Sales:
    return Sales(erp)
