"""Conversores de DTOs de domínio para DTOs HTTP, usados por mais de um router ou endpoint."""
from __future__ import annotations

from src.ai.schemas import SinaisDoSKU, SinalCorpus, SugestaoComSinais, TrechoClassificado, VerificacaoCitacao
from src.api.schemas import (
    AnaliseSKUResponse,
    AvisoResponse,
    CobrancaEntregaResponse,
    DecisaoCompraResponse,
    AvaliacaoTrechoResponse,
    FornecedorResponse,
    GiroResponse,
    SinaisDoSKUResponse,
    SinalCorpusResponse,
    SugestaoComSinaisResponse,
    SugestaoPedidoResponse,
    TrechoClassificadoResponse,
    VerificacaoCitacaoResponse,
)
from src.catalog.schemas import FornecedorParaSKU
from src.ficha_sku.schemas import Ficha
from src.painel.schemas import Aviso, CobrancaEntrega, DecisaoCompra
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
        cor=ficha.sku.cor,
        tamanho=ficha.sku.tamanho,
        estoque=ficha.estoque,
        em_transito_unidades=ficha.em_transito,
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


def sinal_to_response(sinal: SinalCorpus) -> SinalCorpusResponse:
    return SinalCorpusResponse(
        tipo=sinal.tipo,
        mensagem=sinal.mensagem,
        trechos=sinal.trechos,
        probabilidade=sinal.probabilidade,
    )


def sugestao_com_sinais_to_response(com_sinais: SugestaoComSinais) -> SugestaoComSinaisResponse:
    return SugestaoComSinaisResponse(
        sugestao=sugestao_to_response(com_sinais.sugestao), sinais=_sinais_to_response(com_sinais.sinais)
    )


def sinais_do_sku_to_response(sinais: SinaisDoSKU) -> SinaisDoSKUResponse:
    return SinaisDoSKUResponse(sku_code=sinais.sku_code, sinais=_sinais_to_response(sinais.sinais))


def _sinais_to_response(sinais: list[SinalCorpus] | None) -> list[SinalCorpusResponse] | None:
    return None if sinais is None else [sinal_to_response(s) for s in sinais]


def verificacao_to_response(verificacao: VerificacaoCitacao) -> VerificacaoCitacaoResponse:
    return VerificacaoCitacaoResponse(
        trecho_id=verificacao.trecho_id,
        afirmacao=verificacao.afirmacao,
        veredito=verificacao.veredito,
        confianca=verificacao.confianca,
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


def aviso_to_response(aviso: Aviso) -> AvisoResponse:
    return AvisoResponse(
        id=aviso.id,
        sku_code=aviso.sku_code,
        tipo=aviso.tipo,
        comentario=aviso.comentario,
        avisado_por=aviso.avisado_por,
        criado_em=aviso.criado_em,
    )


def decisao_to_response(decisao: DecisaoCompra) -> DecisaoCompraResponse:
    return DecisaoCompraResponse(
        id=decisao.id,
        sku_code=decisao.sku_code,
        tipo=decisao.tipo,
        quantidade=decisao.quantidade,
        motivo=decisao.motivo,
        comentario=decisao.comentario,
        decidido_por=decisao.decidido_por,
        quantidade_sugerida=decisao.quantidade_sugerida,
        politica_versao=decisao.politica_versao,
        criado_em=decisao.criado_em,
    )


def cobranca_to_response(cobranca: CobrancaEntrega) -> CobrancaEntregaResponse:
    return CobrancaEntregaResponse(
        id=cobranca.id,
        pedido_id=cobranca.pedido_id,
        fornecedor_id=cobranca.fornecedor_id,
        nova_previsao=cobranca.nova_previsao,
        comentario=cobranca.comentario,
        cobrado_por=cobranca.cobrado_por,
        criado_em=cobranca.criado_em,
    )
