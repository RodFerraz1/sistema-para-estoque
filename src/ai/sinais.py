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


@dataclass(frozen=True)
class LimiaresSinais:
    """Calibrados por `scripts/avaliar_sinais.py` com o jev-1.13.0
    (`.scratch/sinais-e-citacoes/issues/01-sinais-do-corpus.md`)."""

    atraso_do_fornecedor: float
    demanda_sazonal: float
    encalhe: float


LIMIARES_SINAIS = LimiaresSinais(atraso_do_fornecedor=0.90, demanda_sazonal=0.80, encalhe=0.60)


class SinaisCorpus:
    def __init__(self, busca: BuscaContexto, decisao: DecisionModel) -> None:
        self._busca = busca
        self._decisao = decisao

    def para_sugestao(self, sugestao: SugestaoPedido, sku: SKU) -> list[SinalCorpus]:
        """Sugestão sem fornecedor não tem sinal. Propaga `DecisaoIndisponivel`."""
        if sugestao.fornecedor is None:
            return []
        sinais, _ = self._sinais(sugestao.fornecedor.fornecedor_nome, _produto(sku))
        return sinais

    def para_sugestoes(
        self, pares: Sequence[tuple[SugestaoPedido, SKU]]
    ) -> dict[str, list[SinalCorpus]]:
        """Sinais por `sku_code`, calculados uma vez por par (fornecedor, produto)."""
        return self.para_sugestoes_com_trechos(pares).por_sku

    def para_sugestoes_com_trechos(self, pares: Sequence[tuple[SugestaoPedido, SKU]]) -> SinaisDasSugestoes:
        """Como `para_sugestoes`, com os trechos de origem dos sinais, para quem precisa
        mostrar ou citar esses trechos."""
        calculados: dict[tuple[str, ProdutoDoSinal], tuple[list[SinalCorpus], list[TrechoClassificado]]] = {}
        por_sku: dict[str, list[SinalCorpus]] = {}
        for sugestao, sku in pares:
            if sugestao.fornecedor is None:
                por_sku[sugestao.sku_code] = []
                continue
            par = (sugestao.fornecedor.fornecedor_nome, _produto(sku))
            if par not in calculados:
                calculados[par] = self._sinais(*par)
            por_sku[sugestao.sku_code] = calculados[par][0]
        trechos: dict[str, TrechoClassificado] = {}
        for sinais, avaliados in calculados.values():
            por_id = {t.id: t for t in avaliados}
            for trecho_id in (i for sinal in sinais for i in sinal.trechos):
                trechos.setdefault(trecho_id, por_id[trecho_id])
        return SinaisDasSugestoes(por_sku=por_sku, trechos=list(trechos.values()))

    def _sinais(
        self, fornecedor: str, produto: ProdutoDoSinal
    ) -> tuple[list[SinalCorpus], list[TrechoClassificado]]:
        """Os sinais e os trechos que foram ao modelo de decisão."""
        consulta = f"{fornecedor} e {produto.nome}: atrasos de entrega, vendas por época do ano e estoque encalhado"
        resultado = self._busca.buscar(consulta, k=K_SINAIS, com_conflitos=False)
        trechos = sorted(
            (t for t in resultado.trechos if t.classificacao != "descartado"),
            key=lambda t: t.similaridade,
            reverse=True,
        )[:MAX_TRECHOS_SINAIS]
        if not trechos:
            return [], []
        avaliacoes = self._decisao.avaliar_sinais(fornecedor, produto, trechos)
        sinais = [
            sinal
            for tipo in get_args(TipoSinal)
            if (sinal := _sinal(tipo, fornecedor, produto, avaliacoes)) is not None
        ]
        return sinais, trechos


def _sinal(
    tipo: TipoSinal, fornecedor: str, produto: ProdutoDoSinal, avaliacoes: Sequence[AvaliacaoSinais]
) -> SinalCorpus | None:
    limiar = getattr(LIMIARES_SINAIS, tipo)
    acima = sorted(
        (a for a in avaliacoes if getattr(a, tipo) > limiar),
        key=lambda a: getattr(a, tipo),
        reverse=True,
    )
    if not acima:
        return None
    return SinalCorpus(
        tipo=tipo,
        mensagem=_mensagem(tipo, fornecedor, produto),
        trechos=[a.trecho_id for a in acima],
        probabilidade=getattr(acima[0], tipo),
    )


def _mensagem(tipo: TipoSinal, fornecedor: str, produto: ProdutoDoSinal) -> str:
    if tipo == "atraso_do_fornecedor":
        return f"Os documentos relatam atraso de entrega da {fornecedor}."
    if tipo == "demanda_sazonal":
        return f"Os documentos relatam venda forte de {produto.nome} em alguma época do ano."
    return f"Os documentos relatam encalhe de {produto.nome} ou da categoria dele numa compra anterior."


def _produto(sku: SKU) -> ProdutoDoSinal:
    return ProdutoDoSinal(nome=sku.produto_nome, categoria=sku.categoria)
