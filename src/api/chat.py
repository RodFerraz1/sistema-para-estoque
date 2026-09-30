"""Endpoint HTTP do chat do Copilot."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from src.ai.chat import Copilot, RespostaCopilot
from src.ai.dependencies import get_copilot
from src.ai.identificacao import Identificacao
from src.ai.schemas import Entendimento, Escolha
from src.api.conversores import ficha_to_response, sugestao_to_response, trecho_to_response
from src.api.schemas import (
    EntendimentoResponse,
    EscolhaResponse,
    IdentificacaoResponse,
    PerguntaChatRequest,
    RespostaChatResponse,
)

router = APIRouter(prefix="/chat", tags=["chat"])


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
        sugestoes=[sugestao_to_response(s) for s in resposta.sugestoes],
        trechos=[trecho_to_response(t) for t in resposta.trechos],
        conflitos=resposta.conflitos,
        redator=resposta.redator,
        registro_id=resposta.registro_id,
    )


@router.post("", response_model=RespostaChatResponse)
def chat(
    corpo: PerguntaChatRequest,
    copilot: Copilot = Depends(get_copilot),
) -> RespostaChatResponse:
    return _to_response(copilot.responder(corpo.pergunta))
