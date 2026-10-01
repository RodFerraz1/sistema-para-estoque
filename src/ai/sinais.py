"""Sinais do corpus sobre o fornecedor e o produto de uma sugestão de pedido (ADR-0002):
a busca acha os trechos, o Jev responde trecho a trecho e o código decide o que vira
sinal. Os sinais acompanham a sugestão e nunca alteram a quantidade.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import get_args

from src.ai.busca import BuscaContexto
from src.ai.decisao import DecisionModel
from src.ai.schemas import (
    AvaliacaoSinais,
    ProdutoDoSinal,
    SinaisDasSugestoes,
    SinalCorpus,
    TipoSinal,
    TrechoClassificado,
)
from src.catalog.schemas import SKU
from src.purchasing.schemas import SugestaoPedido

K_SINAIS = 15
MAX_TRECHOS_SINAIS = 10

# Recalibrados pela regra de calibração do M8 (`scripts/avaliar_sinais.py` sobre as
# respostas do jev-1.13.0 gravadas no M6): atraso e encalhe pelo ponto médio, venda
# por época pelo meio da faixa de mais acertos
# (`.scratch/refinamentos/issues/04-regra-de-calibracao.md`).
LIMIARES_SINAIS: dict[TipoSinal, float] = {"atraso_do_fornecedor": 0.80, "demanda_sazonal": 0.75, "encalhe": 0.55}

_MENSAGENS: dict[TipoSinal, str] = {
    "atraso_do_fornecedor": "Os documentos relatam atraso de entrega da {fornecedor}.",
    "demanda_sazonal": "Os documentos relatam venda forte de {produto} em alguma época do ano.",
    "encalhe": "Os documentos relatam encalhe de {produto} ou da categoria dele numa compra anterior.",
}


@dataclass(frozen=True)
class _SinaisDoPar:
    """Os sinais de um par (fornecedor, produto) e os trechos que foram ao modelo de decisão."""

    sinais: list[SinalCorpus]
    avaliados: list[TrechoClassificado]


class SinaisCorpus:
    def __init__(self, busca: BuscaContexto, decisao: DecisionModel) -> None:
        self._busca = busca
        self._decisao = decisao

    def para_sugestao(self, sugestao: SugestaoPedido, sku: SKU) -> list[SinalCorpus]:
        """Sugestão sem fornecedor não tem sinal. Propaga `DecisaoIndisponivel`."""
        if sugestao.fornecedor is None:
            return []
        return self._sinais(sugestao.fornecedor.fornecedor_nome, _produto(sku)).sinais

    def para_sugestoes(self, pares: Sequence[tuple[SugestaoPedido, SKU]]) -> SinaisDasSugestoes:
        """Sinais por `sku_code`, calculados uma vez por par (fornecedor, produto), com os
        trechos de origem para quem precisa mostrar ou citar esses trechos. Propaga
        `DecisaoIndisponivel`."""
        calculados: dict[tuple[str, ProdutoDoSinal], _SinaisDoPar] = {}
        por_sku: dict[str, list[SinalCorpus]] = {}
        for sugestao, sku in pares:
            if sugestao.fornecedor is None:
                por_sku[sugestao.sku_code] = []
                continue
            par = (sugestao.fornecedor.fornecedor_nome, _produto(sku))
            if par not in calculados:
                calculados[par] = self._sinais(*par)
            por_sku[sugestao.sku_code] = calculados[par].sinais
        trechos: dict[str, TrechoClassificado] = {}
        for do_par in calculados.values():
            por_id = {t.id: t for t in do_par.avaliados}
            for trecho_id in (i for sinal in do_par.sinais for i in sinal.trechos):
                trechos.setdefault(trecho_id, por_id[trecho_id])
        return SinaisDasSugestoes(por_sku=por_sku, trechos_de_origem=list(trechos.values()))

    def _sinais(self, fornecedor: str, produto: ProdutoDoSinal) -> _SinaisDoPar:
        consulta = f"{fornecedor} e {produto.nome}: atrasos de entrega, vendas por época do ano e estoque encalhado"
        resultado = self._busca.buscar(consulta, k=K_SINAIS, com_conflitos=False)
        trechos = sorted(
            (t for t in resultado.trechos if t.classificacao != "descartado"),
            key=lambda t: t.similaridade,
            reverse=True,
        )[:MAX_TRECHOS_SINAIS]
        if not trechos:
            return _SinaisDoPar([], [])
        avaliacoes = self._decisao.avaliar_sinais(fornecedor, produto, trechos)
        sinais = [
            sinal
            for tipo in get_args(TipoSinal)
            if (sinal := _sinal(tipo, fornecedor, produto, avaliacoes)) is not None
        ]
        return _SinaisDoPar(sinais, trechos)


def _sinal(
    tipo: TipoSinal, fornecedor: str, produto: ProdutoDoSinal, avaliacoes: Sequence[AvaliacaoSinais]
) -> SinalCorpus | None:
    acima = sorted(
        (a for a in avaliacoes if a.probabilidades[tipo] > LIMIARES_SINAIS[tipo]),
        key=lambda a: a.probabilidades[tipo],
        reverse=True,
    )
    if not acima:
        return None
    return SinalCorpus(
        tipo=tipo,
        mensagem=_MENSAGENS[tipo].format(fornecedor=fornecedor, produto=produto.nome),
        trechos=[a.trecho_id for a in acima],
        probabilidade=acima[0].probabilidades[tipo],
    )


def _produto(sku: SKU) -> ProdutoDoSinal:
    return ProdutoDoSinal(nome=sku.produto_nome, categoria=sku.categoria)
