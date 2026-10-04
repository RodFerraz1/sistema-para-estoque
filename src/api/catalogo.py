"""Endpoints HTTP do módulo `catalog` que alimentam os filtros das telas do comprador."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.schemas import FornecedorResumoResponse
from src.catalog.dependencies import get_catalog
from src.catalog.service import Catalog
from src.usuarios.dependencies import exige_papel

router = APIRouter(tags=["catalog"], dependencies=[Depends(exige_papel("comprador"))])


@router.get("/categorias", response_model=list[str])
def categorias(catalog: Catalog = Depends(get_catalog)) -> list[str]:
    """As categorias com algum SKU ativo, em ordem alfabética."""
    return catalog.categorias()


@router.get("/fornecedores", response_model=list[FornecedorResumoResponse])
def fornecedores(catalog: Catalog = Depends(get_catalog)) -> list[FornecedorResumoResponse]:
    """Os fornecedores que vendem algum SKU ativo, pelo nome."""
    return [FornecedorResumoResponse(id=id_, nome=nome) for id_, nome in catalog.fornecedores_com_sku_ativo()]
