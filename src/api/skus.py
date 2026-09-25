"""Endpoints HTTP sobre SKU."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.schemas import (
    AnaliseSKUResponse,
    FornecedorResponse,
    GiroResponse,
    SKUAbaixoDoPisoResponse,
    VendaMensalResponse,
)
from src.catalog.dependencies import get_catalog
from src.catalog.schemas import SKU, FornecedorParaSKU
from src.catalog.service import Catalog
from src.ficha_sku.dependencies import get_ficha_sku
from src.ficha_sku.schemas import Ficha
from src.ficha_sku.service import FichaSKU, SKUSemEstoque
from src.inventory.dependencies import get_inventory
from src.inventory.service import Inventory
from src.sales.dependencies import get_sales
from src.sales.service import Sales

router = APIRouter(prefix="/skus", tags=["skus"])


def _fornecedor_to_response(f: FornecedorParaSKU) -> FornecedorResponse:
    return FornecedorResponse(
        fornecedor_id=f.fornecedor_id,
        fornecedor_nome=f.fornecedor_nome,
        preco_unitario_reais=f.preco_unitario_reais,
        moq_unidades=f.moq_unidades,
        lead_time_dias_contratado=f.lead_time_dias_contratado,
        lead_time_dias_observado=f.lead_time_dias_observado,
        prazo_pagamento_padrao=f.prazo_pagamento_padrao,
        pedido_minimo_reais=f.pedido_minimo_reais,
    )


def _ficha_to_response(ficha: Ficha) -> AnaliseSKUResponse:
    return AnaliseSKUResponse(
        sku_code=ficha.sku.sku_code,
        produto_nome=ficha.sku.produto_nome,
        categoria=ficha.sku.categoria,
        estoque=ficha.estoque,
        giro=GiroResponse(
            unidades_por_mes=ficha.giro.unidades_por_mes,
            meses_considerados=ficha.giro.meses_considerados,
        ),
        cobertura=ficha.cobertura,
        fornecedores=[_fornecedor_to_response(f) for f in ficha.fornecedores],
    )


def _sku_nao_encontrado(sku_code: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"SKU '{sku_code}' não encontrado",
    )


def _sku_ou_404(catalog: Catalog, sku_code: str) -> SKU:
    sku = catalog.carregar_sku(sku_code)
    if sku is None:
        raise _sku_nao_encontrado(sku_code)
    return sku


@router.get("/abaixo-do-piso", response_model=list[SKUAbaixoDoPisoResponse])
def abaixo_do_piso(
    dias: int = Query(20, ge=1, description="Piso em dias de cobertura"),
    inventory: Inventory = Depends(get_inventory),
) -> list[SKUAbaixoDoPisoResponse]:
    return [
        SKUAbaixoDoPisoResponse(
            sku_code=a.sku_code,
            produto_nome=a.produto_nome,
            cobertura_meses=a.cobertura_meses,
        )
        for a in inventory.abaixo_do_piso(dias_piso=dias)
    ]


@router.get("/{sku_code}/analise", response_model=AnaliseSKUResponse)
def analise_sku(
    sku_code: str,
    ficha_sku: FichaSKU = Depends(get_ficha_sku),
) -> AnaliseSKUResponse:
    try:
        ficha = ficha_sku.completa(sku_code)
    except SKUSemEstoque as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e
    if ficha is None:
        raise _sku_nao_encontrado(sku_code)
    return _ficha_to_response(ficha)


@router.get("/{sku_code}/vendas", response_model=list[VendaMensalResponse])
def historico_vendas(
    sku_code: str,
    meses: int = Query(12, ge=1, le=120),
    catalog: Catalog = Depends(get_catalog),
    sales: Sales = Depends(get_sales),
) -> list[VendaMensalResponse]:
    _sku_ou_404(catalog, sku_code)
    return [
        VendaMensalResponse(
            ano=v.ano,
            mes=v.mes,
            quantidade_unidades=v.quantidade_unidades,
            valor_total_reais=v.valor_total_reais,
        )
        for v in sales.historico_vendas(sku_code, meses=meses)
    ]


@router.get("/{sku_code}/sazonalidade", response_model=dict[int, float])
def sazonalidade(
    sku_code: str,
    catalog: Catalog = Depends(get_catalog),
    sales: Sales = Depends(get_sales),
) -> dict[int, float]:
    _sku_ou_404(catalog, sku_code)
    return sales.sazonalidade(sku_code).multiplicadores


@router.get("/{sku_code}/fornecedores", response_model=list[FornecedorResponse])
def fornecedores_do_sku(
    sku_code: str,
    catalog: Catalog = Depends(get_catalog),
) -> list[FornecedorResponse]:
    _sku_ou_404(catalog, sku_code)
    return [_fornecedor_to_response(f) for f in catalog.fornecedores_de(sku_code)]
