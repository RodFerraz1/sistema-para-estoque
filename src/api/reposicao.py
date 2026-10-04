"""Endpoints HTTP do módulo `reposicao`: o painel do repositor, as verificações de gôndola,
os avisos de gôndola vazia, os setores da loja e o mix de gôndola."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.conversores import verificacao_gondola_to_response
from src.api.schemas import (
    AvisoDeGondolaNoPainelResponse,
    AvisoGondolaResponse,
    AvisoNoPainelResponse,
    CapacidadeGondolaResponse,
    CriarSetorRequest,
    DiaObservadoResponse,
    GravarCapacidadeRequest,
    MixDeGondolaResponse,
    MudarSetorRequest,
    PainelDoRepositorResponse,
    ProdutoDaGondolaResponse,
    QuedaDeVendaResponse,
    QuedaNoAvisoResponse,
    RegistrarAvisoGondolaRequest,
    RegistrarVerificacaoGondolaRequest,
    SetorDoSkuResponse,
    SetorResponse,
    SetorResumoResponse,
    SkuNoMixResponse,
    VerificacaoGondolaResponse,
)
from src.api.skus import sku_ou_404
from src.catalog.dependencies import get_catalog
from src.catalog.service import Catalog, SKUInativo, SKUNaoEncontrado
from src.reposicao.dependencies import get_reposicao
from src.reposicao.repositorio import SetorJaExiste
from src.reposicao.schemas import (
    FiltroReposicao,
    ItemAvisoGondola,
    ItemQuedaDeVenda,
    ProdutoDaGondola,
    QuedaDeVenda,
    Setor,
)
from src.reposicao.service import ProdutoNaoEncontrado, Reposicao, SetorInativo, SetorNaoEncontrado
from src.usuarios.dependencies import exige_papel
from src.usuarios.schemas import Usuario

router = APIRouter(tags=["reposicao"])

REPOSICAO = [Depends(exige_papel("reposicao"))]
QUEM_VE_VERIFICACOES = [Depends(exige_papel("comprador", "reposicao"))]
QUEM_VE_SETOR_DO_SKU = [Depends(exige_papel("vendas", "reposicao"))]
QUEM_VE_O_MIX = [Depends(exige_papel("comprador", "reposicao"))]
ADMIN = [Depends(exige_papel("admin"))]


def _setor(setor: Setor | None) -> SetorResumoResponse | None:
    return None if setor is None else SetorResumoResponse(id=setor.id, nome=setor.nome, ativo=setor.ativo)


def _queda(queda: QuedaDeVenda) -> QuedaNoAvisoResponse:
    return QuedaNoAvisoResponse(
        venda_diaria_base=queda.venda_diaria_base,
        ultimos_dias=[DiaObservadoResponse(dia=d.dia, quantidade=d.quantidade) for d in queda.ultimos_dias],
        vendido_na_janela=queda.vendido_na_janela,
        venda_perdida=queda.venda_perdida,
    )


def _queda_to_response(item: ItemQuedaDeVenda) -> QuedaDeVendaResponse:
    return QuedaDeVendaResponse(
        sku_code=item.sku.sku_code,
        produto_id=item.sku.produto_id,
        produto_nome=item.sku.produto_nome,
        cor=item.sku.cor,
        tamanho=item.sku.tamanho,
        categoria=item.sku.categoria,
        disponivel=item.disponivel,
        setor=_setor(item.setor),
        **_queda(item.queda).model_dump(),
    )


def _aviso_no_painel_to_response(item: ItemAvisoGondola) -> AvisoDeGondolaNoPainelResponse:
    return AvisoDeGondolaNoPainelResponse(
        sku_code=item.sku.sku_code,
        produto_id=item.sku.produto_id,
        produto_nome=item.sku.produto_nome,
        cor=item.sku.cor,
        tamanho=item.sku.tamanho,
        categoria=item.sku.categoria,
        disponivel=item.disponivel,
        setor=_setor(item.setor),
        avisos=[
            AvisoNoPainelResponse(id=a.id, avisado_por=a.avisado_por, comentario=a.comentario, criado_em=a.criado_em)
            for a in item.avisos
        ],
        queda=_queda(item.queda) if item.queda else None,
    )


@router.get("/reposicao/painel", response_model=PainelDoRepositorResponse, dependencies=REPOSICAO)
def painel(
    busca: Annotated[str | None, Query(max_length=100)] = None,
    categoria: str | None = None,
    setor: UUID | None = None,
    reposicao: Reposicao = Depends(get_reposicao),
) -> PainelDoRepositorResponse:
    """Os SKUs que provavelmente faltam na gôndola. Primeiro os avisos de gôndola vazia das
    vendedoras ainda sem verificação, do mais antigo para o mais recente; depois a queda de
    venda nos últimos dias abertos com estoque disponível no ERP, da maior venda perdida para
    a menor. Um SKU com os dois fica só nos avisos, com a `queda`. `busca` segue a regra de
    `/painel`; `setor` filtra pelo setor conhecido do SKU. 503 com o banco fora do ar."""
    resultado = reposicao.painel(FiltroReposicao(busca=busca, categoria=categoria, setor_id=setor))
    return PainelDoRepositorResponse(
        avisos_de_gondola=[_aviso_no_painel_to_response(i) for i in resultado.avisos_de_gondola],
        quedas_de_venda=[_queda_to_response(i) for i in resultado.quedas_de_venda],
    )


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
    do painel do repositor até um dia aberto inteiro fechar ainda com queda de venda. Fecha os
    avisos de gôndola vazia abertos do SKU e notifica cada vendedora que avisou. `setor_id`
    corrige o setor conhecido do SKU. `sem_estoque_no_deposito` com disponível no ERP põe o
    SKU em estoque divergente no painel do comprador. 404 sem o SKU, 422 com o SKU inativo
    ou com o setor desconhecido ou inativo."""
    try:
        verificacao = reposicao.registrar_verificacao(
            sku_code, corpo.resultado, usuario, corpo.comentario, corpo.setor_id
        )
    except SKUNaoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except (SKUInativo, SetorNaoEncontrado, SetorInativo) as e:
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


@router.post("/avisos-gondola", response_model=AvisoGondolaResponse, status_code=status.HTTP_201_CREATED)
def registrar_aviso_gondola(
    corpo: RegistrarAvisoGondolaRequest,
    usuario: Usuario = Depends(exige_papel("vendas")),
    reposicao: Reposicao = Depends(get_reposicao),
) -> AvisoGondolaResponse:
    """A vendedora avisa o repositor que a gôndola do SKU está vazia. Grava quem avisou pelo
    usuário logado e o disponível do ERP no momento, mesmo zero. O SKU entra no topo do
    painel do repositor e o papel `reposicao` é notificado na hora. O setor vira o setor
    conhecido do SKU. 404 sem o SKU, 422 com o SKU inativo ou com o setor desconhecido ou
    inativo."""
    try:
        aviso = reposicao.registrar_aviso_gondola(corpo.sku_code, corpo.setor_id, usuario, corpo.comentario)
    except SKUNaoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except (SKUInativo, SetorNaoEncontrado, SetorInativo) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)) from e
    return AvisoGondolaResponse(
        id=aviso.id,
        sku_code=aviso.sku_code,
        setor_id=aviso.setor_id,
        comentario=aviso.comentario,
        disponivel_no_erp=aviso.disponivel_no_erp,
        avisado_por=aviso.avisado_por,
        criado_em=aviso.criado_em,
    )


@router.get("/skus/{sku_code}/setor", response_model=SetorDoSkuResponse, dependencies=QUEM_VE_SETOR_DO_SKU)
def setor_do_sku(sku_code: str, reposicao: Reposicao = Depends(get_reposicao)) -> SetorDoSkuResponse:
    """O setor conhecido do SKU, ativo ou não: o do último aviso de gôndola vazia ou o que a
    verificação corrigiu. Nulo quando ninguém disse ainda. 404 sem o SKU."""
    try:
        return SetorDoSkuResponse(sku_code=sku_code, setor=_setor(reposicao.setor_do_sku(sku_code)))
    except SKUNaoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


def _setor_to_response(setor: Setor, skus_por_setor: dict[UUID, int]) -> SetorResponse:
    return SetorResponse(id=setor.id, nome=setor.nome, ativo=setor.ativo, skus_conhecidos=skus_por_setor.get(setor.id, 0))


@router.get("/setores", response_model=list[SetorResponse])
def setores(
    usuario: Usuario = Depends(exige_papel("admin", "vendas", "reposicao")),
    reposicao: Reposicao = Depends(get_reposicao),
) -> list[SetorResponse]:
    """Pelo nome. O admin vê todos; a vendedora e o repositor, só os ativos."""
    contagem = reposicao.skus_por_setor()
    return [
        _setor_to_response(s, contagem)
        for s in reposicao.setores()
        if s.ativo or "admin" in usuario.papeis
    ]


@router.post("/setores", response_model=SetorResponse, status_code=status.HTTP_201_CREATED, dependencies=ADMIN)
def criar_setor(corpo: CriarSetorRequest, reposicao: Reposicao = Depends(get_reposicao)) -> SetorResponse:
    """Nasce ativo. 409 com o nome de outro setor (sem diferenciar maiúsculas), 422 sem nome."""
    try:
        return _setor_to_response(reposicao.criar_setor(corpo.nome), {})
    except SetorJaExiste as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.put("/setores/{setor_id}", response_model=SetorResponse, dependencies=ADMIN)
def mudar_setor(
    setor_id: UUID, corpo: MudarSetorRequest, reposicao: Reposicao = Depends(get_reposicao)
) -> SetorResponse:
    """Renomeia, desativa ou reativa. O setor desativado some da lista da vendedora e do
    repositor, mas continua nos avisos e no setor conhecido dos SKUs. 404 sem o setor, 409
    com o nome de outro setor, 422 sem nome."""
    try:
        setor = reposicao.mudar_setor(setor_id, corpo.nome, corpo.ativo)
    except SetorNaoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except SetorJaExiste as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    return _setor_to_response(setor, reposicao.skus_por_setor())


def _produto_to_response(produto: ProdutoDaGondola) -> ProdutoDaGondolaResponse:
    return ProdutoDaGondolaResponse(
        produto_id=produto.produto_id,
        produto_nome=produto.produto_nome,
        categoria=produto.categoria,
        skus=produto.skus,
        capacidade=produto.capacidade.capacidade if produto.capacidade else None,
    )


@router.get("/reposicao/produtos", response_model=list[ProdutoDaGondolaResponse], dependencies=REPOSICAO)
def produtos(
    busca: Annotated[str | None, Query(max_length=100)] = None,
    reposicao: Reposicao = Depends(get_reposicao),
) -> list[ProdutoDaGondolaResponse]:
    """Os produtos com SKU ativo, pelo nome, com a capacidade da gôndola gravada. `busca`
    acha o produto pelo código, nome, cor ou tamanho de qualquer SKU dele."""
    return [_produto_to_response(p) for p in reposicao.produtos(busca)]


@router.get("/reposicao/produtos/{produto_id}/mix", response_model=MixDeGondolaResponse, dependencies=QUEM_VE_O_MIX)
def mix(
    produto_id: UUID,
    capacidade: Annotated[int | None, Query(gt=0)] = None,
    reposicao: Reposicao = Depends(get_reposicao),
) -> MixDeGondolaResponse:
    """Para cada SKU ativo do produto, a participação nas vendas dos últimos
    `dias_mix_gondola` dias abertos, a venda média diária, o disponível e quantas peças pôr
    na gôndola. Sem `capacidade`, usa a gravada; sem nenhuma das duas, a `quantidade` vem
    nula. 404 sem SKU ativo do produto."""
    try:
        resultado = reposicao.mix(produto_id, capacidade)
    except ProdutoNaoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    produto = _produto_to_response(resultado.produto)
    return MixDeGondolaResponse(
        produto_id=produto.produto_id,
        produto_nome=produto.produto_nome,
        categoria=produto.categoria,
        capacidade=resultado.capacidade,
        capacidade_gravada=produto.capacidade,
        dias_abertos=resultado.dias_abertos,
        skus=[
            SkuNoMixResponse(
                sku_code=s.sku.sku_code,
                cor=s.sku.cor,
                tamanho=s.sku.tamanho,
                venda_media_diaria=s.venda_media_diaria,
                participacao=s.participacao,
                disponivel=s.disponivel,
                quantidade=s.quantidade,
            )
            for s in resultado.skus
        ],
    )


@router.put("/reposicao/produtos/{produto_id}/capacidade", response_model=CapacidadeGondolaResponse)
def gravar_capacidade(
    produto_id: UUID,
    corpo: GravarCapacidadeRequest,
    usuario: Usuario = Depends(exige_papel("reposicao")),
    reposicao: Reposicao = Depends(get_reposicao),
) -> CapacidadeGondolaResponse:
    """Quantas peças do produto cabem na gôndola, no lugar da anterior. 404 sem SKU ativo do
    produto, 422 com capacidade menor que 1."""
    try:
        gravada = reposicao.gravar_capacidade(produto_id, corpo.capacidade, usuario)
    except ProdutoNaoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return CapacidadeGondolaResponse(
        produto_id=gravada.produto_id, capacidade=gravada.capacidade, atualizado_em=gravada.atualizado_em
    )
