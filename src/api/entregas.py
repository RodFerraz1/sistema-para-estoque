"""Endpoints HTTP das entregas atrasadas: a cobrança de entrega do comprador chefe, as
entregas pendentes de um SKU e o histórico de atrasos de um fornecedor."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.conversores import cobranca_to_response
from src.api.schemas import (
    AtrasoRecebidoResponse,
    CobrancaEntregaResponse,
    EntregaPendenteResponse,
    HistoricoDeAtrasosResponse,
    RegistrarCobrancaRequest,
)
from src.inventory.dependencies import get_inventory
from src.inventory.service import Inventory
from src.painel.dependencies import get_painel
from src.painel.service import NovaPrevisaoNoPassado, Painel, PedidoSemEntregaAtrasada, SKUNaoEncontrado
from src.usuarios.dependencies import exige_papel
from src.usuarios.schemas import Usuario

router = APIRouter(tags=["entregas"])

COMPRADOR = [Depends(exige_papel("comprador"))]


@router.post(
    "/pedidos/{pedido_id}/cobrancas", response_model=CobrancaEntregaResponse, status_code=status.HTTP_201_CREATED
)
def registrar_cobranca(
    pedido_id: UUID,
    corpo: RegistrarCobrancaRequest,
    usuario: Usuario = Depends(exige_papel("comprador")),
    painel: Painel = Depends(get_painel),
) -> CobrancaEntregaResponse:
    """Grava quem cobrou pelo usuário logado. Vale para o pedido inteiro e o tira do painel
    até a nova previsão ou, sem ela, por 7 dias. O ERP não muda. 404 para pedido sem entrega
    atrasada, 422 com a nova previsão antes de hoje."""
    try:
        cobranca = painel.registrar_cobranca(pedido_id, usuario, corpo.nova_previsao, corpo.comentario)
    except PedidoSemEntregaAtrasada as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NovaPrevisaoNoPassado as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)) from e
    return cobranca_to_response(cobranca)


@router.get("/skus/{sku_code}/entregas", response_model=list[EntregaPendenteResponse], dependencies=COMPRADOR)
def entregas_do_sku(sku_code: str, painel: Painel = Depends(get_painel)) -> list[EntregaPendenteResponse]:
    """O que falta chegar dos pedidos de compra abertos, pela data prevista (sem data por
    último), com as cobranças de cada pedido. 404 sem o SKU."""
    try:
        entregas = painel.entregas_do_sku(sku_code)
    except SKUNaoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return [
        EntregaPendenteResponse(
            pedido_id=e.pedido_id,
            fornecedor_nome=e.fornecedor_nome,
            status=e.status,
            quantidade_pendente=e.quantidade_pendente,
            data_prevista_entrega=e.data_prevista_entrega,
            atrasada=e.atrasada,
            dias_de_atraso=e.dias_de_atraso,
            cobranca_vigente=e.cobranca_vigente,
            cobrancas=[cobranca_to_response(c) for c in e.cobrancas],
        )
        for e in entregas
    ]


@router.get("/fornecedores/{fornecedor_id}/atrasos", response_model=HistoricoDeAtrasosResponse, dependencies=COMPRADOR)
def atrasos_do_fornecedor(
    fornecedor_id: UUID, inventory: Inventory = Depends(get_inventory)
) -> HistoricoDeAtrasosResponse:
    """As entregas recebidas (`recebido_total`) e as que chegaram depois da data prevista,
    com a média de dias de atraso. 404 sem o fornecedor."""
    historico = inventory.atrasos_do_fornecedor(fornecedor_id)
    if historico is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Fornecedor '{fornecedor_id}' não encontrado")
    return HistoricoDeAtrasosResponse(
        fornecedor_id=historico.fornecedor_id,
        fornecedor_nome=historico.fornecedor_nome,
        entregas_recebidas=historico.entregas_recebidas,
        entregas_atrasadas=len(historico.atrasos),
        media_dias_de_atraso=historico.media_dias_de_atraso,
        atrasos=[AtrasoRecebidoResponse(**a.model_dump()) for a in historico.atrasos],
    )
