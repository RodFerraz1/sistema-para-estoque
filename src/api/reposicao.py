"""Endpoints HTTP do módulo `reposicao`: o painel do repositor."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.api.schemas import DiaObservadoResponse, PainelDoRepositorResponse, QuedaDeVendaResponse
from src.reposicao.dependencies import get_reposicao
from src.reposicao.schemas import FiltroReposicao, ItemQuedaDeVenda
from src.reposicao.service import Reposicao
from src.usuarios.dependencies import exige_papel

router = APIRouter(tags=["reposicao"])

REPOSICAO = [Depends(exige_papel("reposicao"))]


def _queda_to_response(item: ItemQuedaDeVenda) -> QuedaDeVendaResponse:
    return QuedaDeVendaResponse(
        sku_code=item.sku.sku_code,
        produto_nome=item.sku.produto_nome,
        cor=item.sku.cor,
        tamanho=item.sku.tamanho,
        categoria=item.sku.categoria,
        disponivel=item.disponivel,
        venda_diaria_base=item.queda.venda_diaria_base,
        ultimos_dias=[DiaObservadoResponse(dia=d.dia, quantidade=d.quantidade) for d in item.queda.ultimos_dias],
        vendido_na_janela=item.queda.vendido_na_janela,
        venda_perdida=item.queda.venda_perdida,
    )


@router.get("/reposicao/painel", response_model=PainelDoRepositorResponse, dependencies=REPOSICAO)
def painel(
    busca: Annotated[str | None, Query(max_length=100)] = None,
    categoria: str | None = None,
    reposicao: Reposicao = Depends(get_reposicao),
) -> PainelDoRepositorResponse:
    """Os SKUs que provavelmente faltam na gôndola: queda de venda nos últimos dias abertos
    com estoque disponível no ERP, da maior venda perdida para a menor. `busca` segue a regra
    de `/painel`. 503 com o banco fora do ar."""
    resultado = reposicao.painel(FiltroReposicao(busca=busca, categoria=categoria))
    return PainelDoRepositorResponse(quedas_de_venda=[_queda_to_response(i) for i in resultado.quedas_de_venda])
