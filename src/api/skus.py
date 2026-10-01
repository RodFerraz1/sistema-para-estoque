"""Endpoints HTTP sobre SKU."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from src.ai.dependencies import get_sinais_corpus
from src.ai.sinais import SinaisCorpus
from src.api.conversores import (
    ficha_to_response,
    fornecedor_to_response,
    sinal_to_response,
    sugestao_to_response,
)
from src.api.schemas import (
    AnaliseSKUResponse,
    FornecedorResponse,
    SinalCorpusResponse,
    SKUAbaixoDoPisoResponse,
    SugestaoPedidoResponse,
    VendaMensalResponse,
)
from src.catalog.dependencies import get_catalog
from src.catalog.schemas import SKU
from src.catalog.service import Catalog
from src.ficha_sku.dependencies import get_ficha_sku
from src.ficha_sku.service import FichaSKU
from src.inventory.dependencies import get_inventory
from src.inventory.service import Inventory
from src.politica_compra.dependencies import get_politica_compra_repositorio
from src.politica_compra.repositorio import PoliticaCompraRepositorio
from src.purchasing.dependencies import get_purchasing
from src.purchasing.service import Purchasing
from src.sales.dependencies import get_sales
from src.sales.service import Sales

router = APIRouter(prefix="/skus", tags=["skus"])


def sku_sem_estoque(request: Request, erro: Exception) -> JSONResponse:
    """Handler de `SKUSemEstoque`: o ERP tem o SKU sem a linha de estoque, um defeito
    dos dados e não do pedido."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": str(erro)}
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
    dias: int | None = Query(
        None,
        ge=1,
        description="Piso de alerta em dias de cobertura. Sem ele, usa o da política ativa.",
    ),
    inventory: Inventory = Depends(get_inventory),
    politicas: PoliticaCompraRepositorio = Depends(get_politica_compra_repositorio),
) -> list[SKUAbaixoDoPisoResponse]:
    if dias is None:
        dias = politicas.ativa().parametros.piso_alerta_dias
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
    ficha = ficha_sku.completa(sku_code)
    if ficha is None:
        raise _sku_nao_encontrado(sku_code)
    return ficha_to_response(ficha)


@router.get("/{sku_code}/sugestao-compra", response_model=SugestaoPedidoResponse)
def sugestao_compra(
    sku_code: str,
    purchasing: Purchasing = Depends(get_purchasing),
) -> SugestaoPedidoResponse:
    sugestao = purchasing.sugerir_pedido(sku_code)
    if sugestao is None:
        raise _sku_nao_encontrado(sku_code)
    return sugestao_to_response(sugestao)


@router.get("/{sku_code}/sugestao-compra/sinais", response_model=list[SinalCorpusResponse])
def sinais_da_sugestao_compra(
    sku_code: str,
    catalog: Catalog = Depends(get_catalog),
    purchasing: Purchasing = Depends(get_purchasing),
    sinais_corpus: SinaisCorpus = Depends(get_sinais_corpus),
) -> list[SinalCorpusResponse]:
    """Sinais do corpus sobre o fornecedor e o produto da sugestão. Lista vazia quando a
    sugestão não tem fornecedor; 503 sem o Jev."""
    sku = _sku_ou_404(catalog, sku_code)
    sugestao = purchasing.sugerir_pedido(sku_code)
    if sugestao is None:
        raise _sku_nao_encontrado(sku_code)
    return [sinal_to_response(s) for s in sinais_corpus.para_sugestao(sugestao, sku)]


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
    return [fornecedor_to_response(f) for f in catalog.fornecedores_de(sku_code)]
