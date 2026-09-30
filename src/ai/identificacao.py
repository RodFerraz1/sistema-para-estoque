"""Identificação dos SKUs de uma pergunta do chat, a partir do entendimento do Jev.

O código de SKU escrito na pergunta ganha sempre. Sem código, o produto escolhido
pelo Jev, com confiança de pelo menos `LIMIAR_PRODUTO`, vira a lista dos SKUs
dele, estreitada pelas cores e pelos tamanhos citados.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Sequence
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.ai.schemas import NENHUM_PRODUTO, Entendimento, ProdutoCatalogo
from src.catalog.schemas import SKU

LIMIAR_PRODUTO = 0.60
MAX_SKUS_POR_RESPOSTA = 12
PROBABILIDADE_MINIMA_CANDIDATO = 0.15
MAX_CANDIDATOS = 3

OrigemIdentificacao = Literal["codigo", "produto", "nenhum"]


class Identificacao(BaseModel):
    """`total_skus` conta os SKUs identificados antes do corte em `MAX_SKUS_POR_RESPOSTA`."""

    model_config = ConfigDict(frozen=True)

    skus: list[str]
    total_skus: int
    origem: OrigemIdentificacao
    produto: str | None
    candidatos: list[str]


def produtos_do_catalogo(skus: Sequence[SKU]) -> list[ProdutoCatalogo]:
    por_produto: dict[UUID, list[SKU]] = {}
    for sku in sorted(skus, key=lambda s: s.sku_code):
        por_produto.setdefault(sku.produto_id, []).append(sku)

    produtos: list[ProdutoCatalogo] = []
    vezes_do_nome: dict[str, int] = {}
    for skus_do_produto in por_produto.values():
        primeiro = skus_do_produto[0]
        vezes_do_nome[primeiro.produto_nome] = vezes_do_nome.get(primeiro.produto_nome, 0) + 1
        vezes = vezes_do_nome[primeiro.produto_nome]
        produtos.append(
            ProdutoCatalogo(
                nome=primeiro.produto_nome if vezes == 1 else f"{primeiro.produto_nome} ({vezes})",
                categoria=primeiro.categoria,
                cores=list(dict.fromkeys(s.cor for s in skus_do_produto)),
                tamanhos=list(dict.fromkeys(s.tamanho for s in skus_do_produto)),
                prefixo=primeiro.sku_code.split("-")[0],
                skus=skus_do_produto,
            )
        )
    return produtos


def identificar_skus(
    pergunta: str, entendimento: Entendimento, produtos: Sequence[ProdutoCatalogo]
) -> Identificacao:
    citados = _codigos_citados(pergunta, produtos)
    if citados:
        return _identificacao(citados, "codigo", None, [])

    escolha = entendimento.produto
    produto = next((p for p in produtos if p.nome == escolha.escolha), None)
    if produto is not None and escolha.confianca >= LIMIAR_PRODUTO:
        palavras = _palavras(pergunta)
        radicais = {_radical_de_cor(palavra) for palavra in palavras}
        skus = _estreitar(produto.skus, lambda sku: _cita_cor(sku.cor, radicais))
        skus = _estreitar(skus, lambda sku: _normalizar(sku.tamanho) in palavras)
        return _identificacao([s.sku_code for s in skus], "produto", produto.nome, [])

    nomes = {p.nome for p in produtos}
    candidatos = sorted(
        (
            (nome, probabilidade)
            for nome, probabilidade in escolha.probabilidades.items()
            if nome != NENHUM_PRODUTO and nome in nomes and probabilidade >= PROBABILIDADE_MINIMA_CANDIDATO
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    return _identificacao([], "nenhum", None, [nome for nome, _ in candidatos[:MAX_CANDIDATOS]])


def _identificacao(
    skus: list[str],
    origem: OrigemIdentificacao,
    produto: str | None,
    candidatos: list[str],
) -> Identificacao:
    return Identificacao(
        skus=skus[:MAX_SKUS_POR_RESPOSTA],
        total_skus=len(skus),
        origem=origem,
        produto=produto,
        candidatos=candidatos,
    )


def _codigos_citados(pergunta: str, produtos: Sequence[ProdutoCatalogo]) -> list[str]:
    # Busca pelos códigos conhecidos, e não por uma regex de formato, porque há
    # códigos com hífen duplo e com acento (CB-OFF--CASAL-08, LT-AZUL-ÚNICO-03).
    texto = _normalizar(pergunta)
    return [
        sku.sku_code
        for produto in produtos
        for sku in produto.skus
        if re.search(rf"(?<![\w-]){re.escape(_normalizar(sku.sku_code))}(?![\w-])", texto)
    ]


def _estreitar(skus: list[SKU], casa: Callable[[SKU], bool]) -> list[SKU]:
    estreitados = [sku for sku in skus if casa(sku)]
    return estreitados or skus


def _cita_cor(cor: str, radicais_da_pergunta: set[str]) -> bool:
    return any(
        _radical_de_cor(parte) in radicais_da_pergunta for parte in re.findall(r"\w+", _normalizar(cor))
    )


def _radical_de_cor(palavra: str) -> str:
    sem_plural = palavra.removesuffix("s")
    return sem_plural[:-1] if sem_plural.endswith(("a", "o")) else sem_plural


def _palavras(texto: str) -> set[str]:
    return set(re.findall(r"\w+", _normalizar(texto)))


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sem_acento.casefold()
