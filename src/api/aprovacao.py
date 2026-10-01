"""Endpoints HTTP da fila de aprovação. `POST /sugestoes/{id}/aprovar` é o único
caminho da API que cria pedido de compra no ERP."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.ai.dependencies import get_sinais_corpus
from src.ai.sinais import SinaisCorpus
from src.api.conversores import faixa_aprovacao_to_response, sugestao_com_sinais_to_response
from src.api.schemas import (
    AprovarSugestaoRequest,
    FaixaAprovacaoResponse,
    RejeitarSugestaoRequest,
    ResultadoGeracaoResponse,
    SugestaoNaFilaResponse,
)
from src.aprovacao.dependencies import get_aprovacao
from src.aprovacao.schemas import StatusSugestao, SugestaoNaFila
from src.aprovacao.service import (
    Aprovacao,
    JustificativaObrigatoria,
    SugestaoJaDecidida,
    SugestaoNaoEncontrada,
)
from src.purchasing.service import QuantidadeInvalida

router = APIRouter(prefix="/sugestoes", tags=["aprovacao"])


def _to_response(s: SugestaoNaFila) -> SugestaoNaFilaResponse:
    return SugestaoNaFilaResponse(
        id=s.id,
        criado_em=s.criado_em,
        status=s.status,
        destaque=s.destaque,
        sku_code=s.sku_code,
        produto_nome=s.sku.produto_nome,
        cobertura_na_chegada_sem_compra_meses=s.cobertura_na_chegada_sem_compra_meses,
        sugestao=sugestao_com_sinais_to_response(s.sugestao),
        faixa=faixa_aprovacao_to_response(s.faixa),
        decidido_em=s.decidido_em,
        decidido_por=s.decidido_por,
        quantidade_aprovada=s.quantidade_aprovada,
        justificativa=s.justificativa,
        motivo_rejeicao=s.motivo_rejeicao,
        pedido_compra_id=s.pedido_compra_id,
    )


_CODIGOS: dict[type[Exception], int] = {
    SugestaoNaoEncontrada: status.HTTP_404_NOT_FOUND,
    SugestaoJaDecidida: status.HTTP_409_CONFLICT,
    QuantidadeInvalida: status.HTTP_422_UNPROCESSABLE_CONTENT,
    JustificativaObrigatoria: status.HTTP_422_UNPROCESSABLE_CONTENT,
}
_ERROS_DA_DECISAO = tuple(_CODIGOS)


def _http(erro: Exception) -> HTTPException:
    return HTTPException(status_code=_CODIGOS[type(erro)], detail=str(erro))


@router.post("/gerar", response_model=ResultadoGeracaoResponse)
def gerar(
    aprovacao: Aprovacao = Depends(get_aprovacao),
    sinais: SinaisCorpus = Depends(get_sinais_corpus),
) -> ResultadoGeracaoResponse:
    """Sugestão para cada SKU ativo; as com compra substituem as pendentes da fila. Com o
    Jev fora do ar, entram sem sinais e `sinais_indisponiveis` vem verdadeiro. Leva de
    30 a 60 s com o seed."""
    resultado = aprovacao.gerar_fila(sinais)
    return ResultadoGeracaoResponse(
        geradas=resultado.geradas,
        substituidas=resultado.substituidas,
        skus_avaliados=resultado.skus_avaliados,
        sinais_indisponiveis=resultado.sinais_indisponiveis,
    )


@router.get("", response_model=list[SugestaoNaFilaResponse])
def listar(
    status_: StatusSugestao = Query("pendente", alias="status"),
    aprovacao: Aprovacao = Depends(get_aprovacao),
) -> list[SugestaoNaFilaResponse]:
    """Pendentes na ordem da fila (destaque primeiro, depois a mais urgente); as outras,
    da decisão mais recente para a mais antiga."""
    return [_to_response(s) for s in aprovacao.listar(status_)]


@router.get("/{id}", response_model=SugestaoNaFilaResponse)
def carregar(id: UUID, aprovacao: Aprovacao = Depends(get_aprovacao)) -> SugestaoNaFilaResponse:
    sugestao = aprovacao.carregar(id)
    if sugestao is None:
        raise _http(SugestaoNaoEncontrada(id))
    return _to_response(sugestao)


@router.get("/{id}/faixa", response_model=FaixaAprovacaoResponse)
def faixa(
    id: UUID,
    quantidade: int = Query(),
    aprovacao: Aprovacao = Depends(get_aprovacao),
) -> FaixaAprovacaoResponse:
    """Faixa de aprovação da sugestão com esta quantidade, com a versão da política da
    sugestão, sem decidir nada. 404 sem a sugestão, 422 com quantidade zero ou abaixo do
    MOQ."""
    try:
        return faixa_aprovacao_to_response(aprovacao.faixa_para(id, quantidade))
    except _ERROS_DA_DECISAO as e:
        raise _http(e) from e


@router.post("/{id}/aprovar", response_model=SugestaoNaFilaResponse)
def aprovar(
    id: UUID,
    corpo: AprovarSugestaoRequest,
    aprovacao: Aprovacao = Depends(get_aprovacao),
) -> SugestaoNaFilaResponse:
    """Cria o pedido de compra no ERP. 404 sem a sugestão, 409 se ela não está mais
    pendente, 422 com quantidade zero ou abaixo do MOQ ou sem a justificativa que a
    faixa exige."""
    try:
        aprovada = aprovacao.aprovar(id, corpo.aprovado_por, corpo.quantidade, corpo.justificativa)
    except _ERROS_DA_DECISAO as e:
        raise _http(e) from e
    return _to_response(aprovada)


@router.post("/{id}/rejeitar", response_model=SugestaoNaFilaResponse)
def rejeitar(
    id: UUID,
    corpo: RejeitarSugestaoRequest,
    aprovacao: Aprovacao = Depends(get_aprovacao),
) -> SugestaoNaFilaResponse:
    """404 sem a sugestão, 409 se ela não está mais pendente."""
    try:
        rejeitada = aprovacao.rejeitar(id, corpo.rejeitado_por, corpo.motivo)
    except _ERROS_DA_DECISAO as e:
        raise _http(e) from e
    return _to_response(rejeitada)
