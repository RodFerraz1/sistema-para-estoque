"""Endpoint HTTP da busca no corpus com o filtro do Jev."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse

from src.ai.busca import K_PADRAO, BuscaContexto
from src.ai.dependencies import get_busca_contexto
from src.ai.schemas import ResultadoBusca
from src.api.conversores import trecho_to_response
from src.api.schemas import ResultadoBuscaResponse
from src.usuarios.dependencies import exige_papel

router = APIRouter(prefix="/rag", tags=["rag"], dependencies=[Depends(exige_papel("comprador"))])


def decisao_indisponivel(request: Request, erro: Exception) -> JSONResponse:
    """Handler de `DecisaoIndisponivel`: sem o Jev, a busca não sai sem filtro."""
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": str(erro)}
    )


def _to_response(resultado: ResultadoBusca) -> ResultadoBuscaResponse:
    return ResultadoBuscaResponse(
        pergunta=resultado.pergunta,
        modelo=resultado.modelo,
        trechos=[trecho_to_response(t) for t in resultado.trechos],
        conflitos=resultado.conflitos,
    )


@router.get("/busca", response_model=ResultadoBuscaResponse)
def busca(
    q: str = Query(..., min_length=1, max_length=500),
    k: int = Query(K_PADRAO, ge=1, le=40),
    busca_contexto: BuscaContexto = Depends(get_busca_contexto),
) -> ResultadoBuscaResponse:
    return _to_response(busca_contexto.buscar(q, k))
