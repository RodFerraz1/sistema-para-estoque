"""Endpoints HTTP do módulo `painel`: o painel de alertas, os avisos da equipe de vendas
e as decisões de compra do comprador chefe."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.conversores import (
    aviso_to_response,
    cobranca_to_response,
    decisao_to_response,
    verificacao_gondola_to_response,
)
from src.api.schemas import (
    AvisoResponse,
    DecisaoCompraResponse,
    EstoqueResponse,
    FornecedorComAtrasoResponse,
    ItemAlertaResponse,
    ItemDecididoResponse,
    ItemEstoqueResponse,
    PainelResponse,
    PedidoAtrasadoResponse,
    RegistrarAvisoRequest,
    RegistrarDecisaoRequest,
    SKUComEntregaAtrasadaResponse,
)
from src.api.skus import sku_ou_404
from src.catalog.dependencies import get_catalog
from src.catalog.service import Catalog
from src.inventory.schemas import dias_de_cobertura
from src.painel.dependencies import get_painel
from src.painel.schemas import (
    POR_PAGINA_MAXIMO,
    FiltroEstoque,
    FiltroPainel,
    FornecedorComAtraso,
    ItemAlerta,
    ItemDecidido,
    ItemEstoque,
    MotivoDoFiltro,
    OrdemEstoque,
    PedidoAtrasado,
    SituacaoEstoque,
)
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
        grupo=item.grupo,
        parou_de_vender=item.parou_de_vender,
        estoque_divergente=verificacao_gondola_to_response(item.estoque_divergente) if item.estoque_divergente else None,
    )


def _decidido_to_response(item: ItemDecidido) -> ItemDecididoResponse:
    return ItemDecididoResponse(
        sku_code=item.sku.sku_code,
        produto_nome=item.sku.produto_nome,
        cor=item.sku.cor,
        tamanho=item.sku.tamanho,
        decisao=decisao_to_response(item.decisao),
    )


def _pedido_atrasado_to_response(pedido: PedidoAtrasado) -> PedidoAtrasadoResponse:
    return PedidoAtrasadoResponse(
        pedido_id=pedido.pedido_id,
        status=pedido.status,
        data_prevista_entrega=pedido.data_prevista_entrega,
        dias_de_atraso=pedido.dias_de_atraso,
        ultima_cobranca=cobranca_to_response(pedido.ultima_cobranca) if pedido.ultima_cobranca else None,
        skus=[
            SKUComEntregaAtrasadaResponse(
                sku_code=s.sku.sku_code,
                produto_nome=s.sku.produto_nome,
                cor=s.sku.cor,
                tamanho=s.sku.tamanho,
                quantidade_pendente=s.quantidade_pendente,
                disponivel=s.disponivel,
                cobertura_dias=_dias(s.cobertura_meses),
                em_ruptura=s.em_ruptura,
            )
            for s in pedido.skus
        ],
    )


def _fornecedor_com_atraso_to_response(fornecedor: FornecedorComAtraso) -> FornecedorComAtrasoResponse:
    return FornecedorComAtrasoResponse(
        fornecedor_id=fornecedor.fornecedor_id,
        fornecedor_nome=fornecedor.fornecedor_nome,
        tem_sku_em_ruptura=fornecedor.tem_sku_em_ruptura,
        maior_atraso_dias=fornecedor.maior_atraso_dias,
        pedidos=[_pedido_atrasado_to_response(p) for p in fornecedor.pedidos],
    )


def _item_de_estoque_to_response(item: ItemEstoque) -> ItemEstoqueResponse:
    return ItemEstoqueResponse(
        sku_code=item.sku.sku_code,
        produto_nome=item.sku.produto_nome,
        cor=item.sku.cor,
        tamanho=item.sku.tamanho,
        categoria=item.sku.categoria,
        disponivel=item.disponivel,
        em_transito=item.em_transito,
        venda_media_diaria=item.venda_media_diaria,
        cobertura_dias=_dias(item.cobertura_meses),
        em_ruptura=item.em_ruptura,
    )


@router.get("/painel", response_model=PainelResponse, dependencies=COMPRADOR)
def painel(
    busca: Annotated[str | None, Query(max_length=100)] = None,
    categoria: str | None = None,
    motivo: MotivoDoFiltro | None = None,
    fornecedor: UUID | None = None,
    painel: Painel = Depends(get_painel),
) -> PainelResponse:
    """Calculado na hora com a política ativa. 503 com o banco fora do ar. `busca` acha
    todas as palavras no código, produto, cor e tamanho, sem acento nem maiúscula;
    `fornecedor` é o id de um fornecedor que vende o SKU; `motivo` é um motivo de alerta ou
    `aviso`. Busca, categoria e fornecedor filtram também os decididos. As entregas
    atrasadas são as dos SKUs que ficaram nos alertas."""
    filtro = FiltroPainel(busca=busca, categoria=categoria, motivo=motivo, fornecedor_id=fornecedor)
    resultado = painel.painel(filtro)
    return PainelResponse(
        alertas=[_item_to_response(i) for i in resultado.alertas],
        decididos=[_decidido_to_response(i) for i in resultado.decididos],
        skus_com_erro=resultado.skus_com_erro,
        contagens=resultado.contagens,
        entregas_atrasadas=[_fornecedor_com_atraso_to_response(f) for f in resultado.entregas_atrasadas],
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


@router.get("/estoque", response_model=EstoqueResponse, dependencies=COMPRADOR)
def estoque(
    busca: Annotated[str | None, Query(max_length=100)] = None,
    categoria: str | None = None,
    situacao: SituacaoEstoque | None = None,
    ordem: OrdemEstoque = "cobertura",
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=POR_PAGINA_MAXIMO)] = 50,
    painel: Painel = Depends(get_painel),
) -> EstoqueResponse:
    """Todos os SKUs ativos com estoque no ERP, paginados. `busca` segue a regra de
    `/painel`; `situacao` é `em_ruptura`, `sem_venda` ou `com_transito`; `ordem` é
    `cobertura` (a menor primeiro), `venda_diaria` (a maior primeiro) ou `nome`. Página
    depois da última vem vazia, com o total. 503 com o banco fora do ar."""
    filtro = FiltroEstoque(busca=busca, categoria=categoria, situacao=situacao)
    resultado = painel.estoque(filtro, ordem=ordem, pagina=pagina, por_pagina=por_pagina)
    return EstoqueResponse(
        itens=[_item_de_estoque_to_response(i) for i in resultado.itens],
        total=resultado.total,
        pagina=resultado.pagina,
        por_pagina=resultado.por_pagina,
    )
