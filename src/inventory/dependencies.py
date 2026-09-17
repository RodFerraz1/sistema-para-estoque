from __future__ import annotations

from fastapi import Depends

from src.erp_adapter.dependencies import get_erp_adapter
from src.erp_adapter.port import ERPAdapter
from src.inventory.service import Inventory
from src.sales.dependencies import get_sales
from src.sales.service import Sales


def get_inventory(
    erp: ERPAdapter = Depends(get_erp_adapter),
    sales: Sales = Depends(get_sales),
) -> Inventory:
    return Inventory(erp, sales)
