"""Endpoints HTTP do chat do Copilot e dos registros de decisão."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.ai.chat import Copilot
from src.ai.dependencies import get_copilot, get_registros_decisao
from src.ai.registro import RegistrosDecisao
from src.ai.schemas import Entendimento, Escolha, Identificacao, RegistroDecisao, RespostaCopilot
from src.api.conversores import (
    ficha_to_response,
    sinais_do_sku_to_response,
    sugestao_com_sinais_to_response,
    trecho_to_response,
    verificacao_to_response,
)
from src.api.schemas import (
    EntendimentoResponse,
    EscolhaResponse,
    IdentificacaoResponse,
    PerguntaChatRequest,
    RegistroDecisaoResponse,
    RespostaChatResponse,
)
from src.api.skus import sku_ou_404
from src.catalog.dependencies import get_catalog
from src.catalog.service import Catalog
from src.usuarios.dependencies import exige_papel

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(exige_papel("comprador"))])


def _escolha_to_response(escolha: Escolha[str]) -> EscolhaResponse:
    return EscolhaResponse(
        escolha=escolha.escolha,
        confianca=escolha.confianca,
        probabilidades=escolha.probabilidades,
    )


def _entendimento_to_response(entendimento: Entendimento) -> EntendimentoResponse:
    return EntendimentoResponse(
        intencao=_escolha_to_response(entendimento.intencao),
        produto=_escolha_to_response(entendimento.produto),
        modelo=entendimento.modelo,
    )


def _identificacao_to_response(identificacao: Identificacao) -> IdentificacaoResponse:
    return IdentificacaoResponse(
        skus=identificacao.skus,
        total_skus=identificacao.total_skus,
        origem=identificacao.origem,
        produto=identificacao.produto,
        candidatos=identificacao.candidatos,
    )


def _to_response(resposta: RespostaCopilot) -> RespostaChatResponse:
    return RespostaChatResponse(
        resposta=resposta.resposta,
        acao=resposta.acao,
        faixa=resposta.faixa,
        entendimento=_entendimento_to_response(resposta.entendimento),
        identificacao=(
            _identificacao_to_response(resposta.identificacao)
            if resposta.identificacao is not None
            else None
        ),
        fichas=[ficha_to_response(f) for f in resposta.fichas],
        sugestoes=[sugestao_com_sinais_to_response(s) for s in resposta.sugestoes],
        trechos=[trecho_to_response(t) for t in resposta.trechos],
        conflitos=resposta.conflitos,
        citacoes=[verificacao_to_response(c) for c in resposta.citacoes],
        redator=resposta.redator,
        registro_id=resposta.registro_id,
    )


def _registro_to_response(registro: RegistroDecisao) -> RegistroDecisaoResponse:
    return RegistroDecisaoResponse(
        id=registro.id,
        criado_em=registro.criado_em,
        pergunta=registro.pergunta,
        intencao=registro.intencao,
        confianca=registro.confianca,
        faixa=registro.faixa,
        acao=registro.acao,
        skus=registro.skus,
        entendimento=_entendimento_to_response(registro.entendimento),
        trechos=registro.trechos,
        redator=registro.redator,
        resposta=registro.resposta,
        duracao_ms=registro.duracao_ms,
        sinais=[sinais_do_sku_to_response(s) for s in registro.sinais],
        citacoes=[verificacao_to_response(c) for c in registro.citacoes],
        sku_em_contexto=registro.sku_em_contexto,
    )


@router.post("", response_model=RespostaChatResponse)
def chat(
    corpo: PerguntaChatRequest,
    catalog: Catalog = Depends(get_catalog),
    copilot: Copilot = Depends(get_copilot),
) -> RespostaChatResponse:
    """Com `sku_code`, a pergunta sobre situação ou sugestão que não cita produto vale
    para esse SKU. 404 com SKU desconhecido."""
    if corpo.sku_code is not None:
        sku_ou_404(catalog, corpo.sku_code)
    return _to_response(copilot.responder(corpo.pergunta, corpo.sku_code))


@router.get("/registros", response_model=list[RegistroDecisaoResponse])
def listar_registros(
    limite: int = Query(20, ge=1, le=100),
    registros: RegistrosDecisao = Depends(get_registros_decisao),
) -> list[RegistroDecisaoResponse]:
    return [_registro_to_response(r) for r in registros.listar(limite)]
