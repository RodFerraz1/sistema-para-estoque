"""Endpoints HTTP sobre SKU."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.schemas import (
    AnaliseSKUResponse,
    FornecedorResponse,
    GiroResponse,
)
from src.catalog.dependencies import get_catalog
from src.catalog.service import Catalog
from src.inventory.dependencies import get_inventory
from src.inventory.service import Inventory
from src.sales.dependencies import get_sales
from src.sales.service import Sales

router = APIRouter(prefix="/skus", tags=["skus"])


@router.get("/{sku_code}/analise", response_model=AnaliseSKUResponse)
def analise_sku(
    sku_code: str,
    catalog: Catalog = Depends(get_catalog),
    inventory: Inventory = Depends(get_inventory),
    sales: Sales = Depends(get_sales),
) -> AnaliseSKUResponse:
    sku = catalog.buscar_sku_por_codigo(sku_code)
    if sku is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SKU '{sku_code}' não encontrado",
        )

    estoque = inventory.estoque_atual(sku.id)
    if estoque is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SKU '{sku_code}' sem snapshot de estoque",
        )
    giro = sales.giro_medio_mensal(sku.id)
    cobertura = inventory.cobertura_meses(sku.id)
    fornecedores = catalog.list_fornecedores_para_sku(sku.id)

    return AnaliseSKUResponse(
        sku_code=sku.sku_code,
        produto_nome=sku.produto_nome,
        categoria=sku.categoria,
        estoque=estoque,
        giro=GiroResponse(
            unidades_por_mes=giro.unidades_por_mes,
            meses_considerados=giro.meses_considerados,
        ),
        cobertura=cobertura,
        fornecedores=[
            FornecedorResponse(
                fornecedor_id=f.fornecedor_id,
                fornecedor_nome=f.fornecedor_nome,
                preco_unitario_reais=f.preco_unitario_reais,
                moq_unidades=f.moq_unidades,
                lead_time_dias_contratado=f.lead_time_dias_contratado,
                lead_time_dias_observado=f.lead_time_dias_observado,
            )
            for f in fornecedores
        ],
    )
