"""Conversores de DTOs de domínio para DTOs HTTP, usados por mais de um router."""
from __future__ import annotations

from src.ai.schemas import TrechoClassificado
from src.api.schemas import (
    AnaliseSKUResponse,
    AvaliacaoTrechoResponse,
    FornecedorResponse,
    GiroResponse,
    SugestaoPedidoResponse,
    TrechoClassificadoResponse,
)
from src.catalog.schemas import FornecedorParaSKU
from src.ficha_sku.schemas import Ficha
from src.purchasing.schemas import SugestaoPedido


def fornecedor_to_response(f: FornecedorParaSKU) -> FornecedorResponse:
    return FornecedorResponse(
        fornecedor_id=f.fornecedor_id,
        fornecedor_nome=f.fornecedor_nome,
        preco_unitario_reais=f.preco_unitario_reais,
        moq_unidades=f.moq_unidades,
        lead_time_dias_contratado=f.lead_time_dias_contratado,
        lead_time_dias_observado=f.lead_time_dias_observado,
        prazo_pagamento_padrao=f.prazo_pagamento_padrao,
        pedido_minimo_reais=f.pedido_minimo_reais,
    )


def ficha_to_response(ficha: Ficha) -> AnaliseSKUResponse:
    return AnaliseSKUResponse(
        sku_code=ficha.sku.sku_code,
        produto_nome=ficha.sku.produto_nome,
        categoria=ficha.sku.categoria,
        estoque=ficha.estoque,
        giro=GiroResponse(
            unidades_por_mes=ficha.giro.unidades_por_mes,
            meses_considerados=ficha.giro.meses_considerados,
        ),
        cobertura=ficha.cobertura,
        fornecedores=[fornecedor_to_response(f) for f in ficha.fornecedores],
    )


def sugestao_to_response(sugestao: SugestaoPedido) -> SugestaoPedidoResponse:
    return SugestaoPedidoResponse(
        sku_code=sugestao.sku_code,
        quantidade=sugestao.quantidade,
        motivo=sugestao.motivo,
        fornecedor=(
            fornecedor_to_response(sugestao.fornecedor)
            if sugestao.fornecedor is not None
            else None
        ),
        valor_estimado_centavos=sugestao.valor_estimado_centavos,
        calculo=sugestao.calculo,
        alertas=sugestao.alertas,
        politica_versao=sugestao.politica_versao,
    )


def trecho_to_response(trecho: TrechoClassificado) -> TrechoClassificadoResponse:
    return TrechoClassificadoResponse(
        id=trecho.id,
        documento=trecho.documento,
        titulo=trecho.titulo,
        tipo=trecho.tipo,
        data=trecho.data,
        tags=trecho.tags,
        texto=trecho.texto,
        similaridade=trecho.similaridade,
        classificacao=trecho.classificacao,
        motivo_descarte=trecho.motivo_descarte,
        avaliacao=AvaliacaoTrechoResponse(
            relevante=trecho.avaliacao.relevante,
            tem_evidencia=trecho.avaliacao.tem_evidencia,
            contradiz_premissa=trecho.avaliacao.contradiz_premissa,
            tenta_instruir=trecho.avaliacao.tenta_instruir,
        ),
    )
