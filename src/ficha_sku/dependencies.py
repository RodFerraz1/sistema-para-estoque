from __future__ import annotations

from fastapi import Depends

from src.catalog.dependencies import get_catalog
from src.catalog.service import Catalog
from src.ficha_sku.service import FichaSKU
from src.inventory.dependencies import get_inventory
from src.inventory.service import Inventory
from src.sales.dependencies import get_sales
from src.sales.service import Sales


def get_ficha_sku(
    catalog: Catalog = Depends(get_catalog),
    inventory: Inventory = Depends(get_inventory),
    sales: Sales = Depends(get_sales),
) -> FichaSKU:
    return FichaSKU(catalog, inventory, sales)
