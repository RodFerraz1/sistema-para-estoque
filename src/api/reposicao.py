"""Endpoints HTTP do módulo `reposicao`: o painel do repositor e as verificações de gôndola."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.conversores import verificacao_gondola_to_response
from src.api.schemas import (
    DiaObservadoResponse,
    PainelDoRepositorResponse,
    QuedaDeVendaResponse,
    RegistrarVerificacaoGondolaRequest,
    VerificacaoGondolaResponse,
)
from src.api.skus import sku_ou_404
from src.catalog.dependencies import get_catalog
from src.catalog.service import Catalog, SKUInativo, SKUNaoEncontrado
from src.reposicao.dependencies import get_reposicao
from src.reposicao.schemas import FiltroReposicao, ItemQuedaDeVenda
from src.reposicao.service import Reposicao
from src.usuarios.dependencies import exige_papel
from src.usuarios.schemas import Usuario

router = APIRouter(tags=["reposicao"])

REPOSICAO = [Depends(exige_papel("reposicao"))]
QUEM_VE_VERIFICACOES = [Depends(exige_papel("comprador", "reposicao"))]


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


@router.post(
    "/skus/{sku_code}/verificacoes", response_model=VerificacaoGondolaResponse, status_code=status.HTTP_201_CREATED
)
def registrar_verificacao(
    sku_code: str,
    corpo: RegistrarVerificacaoGondolaRequest,
    usuario: Usuario = Depends(exige_papel("reposicao")),
    reposicao: Reposicao = Depends(get_reposicao),
) -> VerificacaoGondolaResponse:
    """Grava quem verificou pelo usuário logado e o disponível do ERP no momento. O SKU sai
    do painel do repositor até um dia aberto inteiro fechar ainda com queda de venda.
    `sem_estoque_no_deposito` com disponível no ERP põe o SKU em estoque divergente no painel
    do comprador. 404 sem o SKU, 422 com o SKU inativo."""
    try:
        verificacao = reposicao.registrar_verificacao(sku_code, corpo.resultado, usuario, corpo.comentario)
    except SKUNaoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except SKUInativo as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)) from e
    return verificacao_gondola_to_response(verificacao)


@router.get(
    "/skus/{sku_code}/verificacoes", response_model=list[VerificacaoGondolaResponse], dependencies=QUEM_VE_VERIFICACOES
)
def verificacoes(
    sku_code: str,
    catalog: Catalog = Depends(get_catalog),
    reposicao: Reposicao = Depends(get_reposicao),
) -> list[VerificacaoGondolaResponse]:
    """Da mais recente para a mais antiga."""
    sku_ou_404(catalog, sku_code)
    return [verificacao_gondola_to_response(v) for v in reposicao.verificacoes(sku_code)]
