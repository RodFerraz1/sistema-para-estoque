"""Endpoints HTTP da política de compra."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.api.schemas import PoliticaCompraResponse
from src.politica_compra.dependencies import get_politica_compra_repositorio
from src.politica_compra.repositorio import PoliticaCompraRepositorio
from src.politica_compra.schemas import ParametrosPolitica, PoliticaCompra
from src.usuarios.dependencies import exige_papel

router = APIRouter(
    prefix="/politica-compra", tags=["politica-compra"], dependencies=[Depends(exige_papel("comprador"))]
)


def _to_response(politica: PoliticaCompra) -> PoliticaCompraResponse:
    return PoliticaCompraResponse(
        versao=politica.versao,
        criada_em=politica.criada_em,
        parametros=politica.parametros,
    )


@router.get("", response_model=PoliticaCompraResponse)
def politica_ativa(
    repo: PoliticaCompraRepositorio = Depends(get_politica_compra_repositorio),
) -> PoliticaCompraResponse:
    return _to_response(repo.ativa())


@router.put(
    "", response_model=PoliticaCompraResponse, status_code=status.HTTP_201_CREATED
)
def salvar_nova_versao(
    parametros: ParametrosPolitica,
    repo: PoliticaCompraRepositorio = Depends(get_politica_compra_repositorio),
) -> PoliticaCompraResponse:
    return _to_response(repo.salvar_nova_versao(parametros))
