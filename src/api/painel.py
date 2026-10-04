"""Endpoints HTTP do módulo `painel`: o painel de alertas, os avisos da equipe de vendas
e as decisões de compra do comprador chefe."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.conversores import aviso_to_response, decisao_to_response
from src.api.schemas import (
    AvisoResponse,
    DecisaoCompraResponse,
    ItemAlertaResponse,
    ItemDecididoResponse,
    PainelResponse,
    RegistrarAvisoRequest,
    RegistrarDecisaoRequest,
)
from src.api.skus import sku_ou_404
from src.catalog.dependencies import get_catalog
from src.catalog.service import Catalog
from src.inventory.schemas import dias_de_cobertura
from src.painel.dependencies import get_painel
from src.painel.schemas import ItemAlerta, ItemDecidido
from src.painel.service import (
    MotivoObrigatorio,
    Painel,
    QuantidadeObrigatoria,
    QuantidadeSoParaComprar,
    SKUInativo,
    SKUNaoEncontrado,
)
from src.usuarios.dependencies import exige_papel
from src.usuarios.schemas import Usuario

router = APIRouter(tags=["painel"])

COMPRADOR = [Depends(exige_papel("comprador"))]


def _dias(meses: float | None) -> float | None:
    return None if meses is None else dias_de_cobertura(meses)


def _item_to_response(item: ItemAlerta) -> ItemAlertaResponse:
    return ItemAlertaResponse(
        sku_code=item.sku.sku_code,
        produto_nome=item.sku.produto_nome,
        cor=item.sku.cor,
        tamanho=item.sku.tamanho,
        disponivel=item.disponivel,
        cobertura_atual_meses=item.cobertura_atual_meses,
        cobertura_atual_dias=_dias(item.cobertura_atual_meses),
        cobertura_na_chegada_sem_compra_meses=item.cobertura_na_chegada_sem_compra_meses,
        cobertura_na_chegada_sem_compra_dias=_dias(item.cobertura_na_chegada_sem_compra_meses),
        motivos=item.motivos,
        quantidade_sugerida=item.quantidade_sugerida,
        fornecedor_sugerido=item.fornecedor_sugerido,
        avisos_abertos=len(item.avisos_abertos),
        ultimo_aviso=aviso_to_response(item.avisos_abertos[0]) if item.avisos_abertos else None,
        so_por_aviso=item.so_por_aviso,
    )


def _decidido_to_response(item: ItemDecidido) -> ItemDecididoResponse:
    return ItemDecididoResponse(
        sku_code=item.sku.sku_code,
        produto_nome=item.sku.produto_nome,
        cor=item.sku.cor,
        tamanho=item.sku.tamanho,
        decisao=decisao_to_response(item.decisao),
    )


@router.get("/painel", response_model=PainelResponse, dependencies=COMPRADOR)
def painel(painel: Painel = Depends(get_painel)) -> PainelResponse:
    """Calculado na hora com a política ativa. 503 com o banco fora do ar."""
    resultado = painel.painel()
    return PainelResponse(
        alertas=[_item_to_response(i) for i in resultado.alertas],
        decididos=[_decidido_to_response(i) for i in resultado.decididos],
        skus_com_erro=resultado.skus_com_erro,
    )


@router.post("/avisos", response_model=AvisoResponse, status_code=status.HTTP_201_CREATED)
def registrar_aviso(
    corpo: RegistrarAvisoRequest,
    usuario: Usuario = Depends(exige_papel("vendas")),
    painel: Painel = Depends(get_painel),
) -> AvisoResponse:
    """Grava quem avisou pelo usuário logado. O SKU entra no painel na hora. 404 sem o SKU,
    422 com o SKU inativo."""
    try:
        aviso = painel.registrar_aviso(corpo.sku_code, corpo.tipo, usuario, corpo.comentario)
    except SKUNaoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except SKUInativo as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)) from e
    return aviso_to_response(aviso)


@router.get("/skus/{sku_code}/avisos", response_model=list[AvisoResponse], dependencies=COMPRADOR)
def avisos_abertos(
    sku_code: str,
    catalog: Catalog = Depends(get_catalog),
    painel: Painel = Depends(get_painel),
) -> list[AvisoResponse]:
    """Os avisos abertos, do mais recente para o mais antigo."""
    sku_ou_404(catalog, sku_code)
    return [aviso_to_response(a) for a in painel.avisos_abertos(sku_code)]


@router.get(
    "/skus/{sku_code}/decisoes", response_model=list[DecisaoCompraResponse], dependencies=COMPRADOR
)
def decisoes(
    sku_code: str,
    catalog: Catalog = Depends(get_catalog),
    painel: Painel = Depends(get_painel),
) -> list[DecisaoCompraResponse]:
    """Da mais recente para a mais antiga."""
    sku_ou_404(catalog, sku_code)
    return [decisao_to_response(d) for d in painel.decisoes(sku_code)]


@router.post("/skus/{sku_code}/decisoes", response_model=DecisaoCompraResponse, status_code=status.HTTP_201_CREATED)
def registrar_decisao(
    sku_code: str,
    corpo: RegistrarDecisaoRequest,
    usuario: Usuario = Depends(exige_papel("comprador")),
    painel: Painel = Depends(get_painel),
) -> DecisaoCompraResponse:
    """Grava quem decidiu pelo usuário logado. Fecha os avisos abertos do SKU e o tira do
    painel por 7 dias, a não ser que chegue aviso novo. Não cria pedido de compra. 404 sem o
    SKU, 422 com `vou_comprar` sem quantidade maior que zero, quantidade em outro tipo ou
    `nao_comprar_agora` sem motivo."""
    try:
        decisao = painel.registrar_decisao(
            sku_code, corpo.tipo, usuario, corpo.quantidade, corpo.motivo, corpo.comentario
        )
    except SKUNaoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except (QuantidadeObrigatoria, QuantidadeSoParaComprar, MotivoObrigatorio) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)) from e
    return decisao_to_response(decisao)
