"""Adapters em memória do módulo `ai`, para testes e para medir o recall sem banco."""
from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping, Sequence
from typing import TypedDict

from src.ai.decisao import DecisaoIndisponivel, DecisionModel
from src.ai.embeddings import DIMENSAO
from src.ai.repositorio import TrechosRepositorio
from src.ai.schemas import (
    AvaliacaoConflito,
    AvaliacaoTrecho,
    Trecho,
    TrechoIndexado,
    TrechoRecuperado,
)


class FakeEmbedder:
    """Soma, por palavra, um 1 numa posição derivada do hash da palavra.

    Textos com palavras em comum ficam parecidos, o que basta para testar
    ordenação sem baixar modelo.
    """

    dimensao = DIMENSAO

    def embed(self, textos: list[str]) -> list[list[float]]:
        return [self._vetor(texto) for texto in textos]

    def _vetor(self, texto: str) -> list[float]:
        vetor = [0.0] * self.dimensao
        for palavra in re.findall(r"\w+", texto.lower()):
            posicao = int.from_bytes(hashlib.sha256(palavra.encode()).digest()[:4]) % self.dimensao
            vetor[posicao] += 1.0
        return vetor


class InMemoryTrechosRepositorio(TrechosRepositorio):
    def __init__(self) -> None:
        self._documentos: dict[str, tuple[str, list[TrechoIndexado]]] = {}

    def hashes_por_documento(self) -> dict[str, str]:
        return {documento: hash_ for documento, (hash_, _) in self._documentos.items()}

    def substituir_documento(
        self, documento: str, hash_documento: str, trechos: list[TrechoIndexado]
    ) -> None:
        if trechos:
            self._documentos[documento] = (hash_documento, list(trechos))
        else:
            self.remover_documento(documento)

    def remover_documento(self, documento: str) -> None:
        self._documentos.pop(documento, None)

    def buscar_similares(self, vetor: list[float], k: int) -> list[TrechoRecuperado]:
        recuperados = [
            TrechoRecuperado(
                **trecho.model_dump(exclude={"embedding"}),
                similaridade=_cosseno(vetor, trecho.embedding),
            )
            for _, trechos in self._documentos.values()
            for trecho in trechos
        ]
        return sorted(recuperados, key=lambda t: t.similaridade, reverse=True)[:k]


def _cosseno(a: list[float], b: list[float]) -> float:
    normas = math.hypot(*a) * math.hypot(*b)
    if normas == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True)) / normas


class Probabilidades(TypedDict, total=False):
    relevante: float
    tem_evidencia: float
    contradiz_premissa: float
    tenta_instruir: float


class InMemoryDecisionModel(DecisionModel):
    """Avaliações configuradas por trecho e por par de trechos, sem rede.

    Probabilidade que não foi configurada para o trecho vem de `padrao`, e o
    que também não está em `padrao` vale 0. Um par é procurado em `conflitos`
    nas duas ordens e, se não estiver lá, vale `conflito_padrao`. Com
    `falhar_trechos` ou `falhar_conflitos`, o método correspondente lança
    `DecisaoIndisponivel` como o Jev fora do ar.
    """

    def __init__(
        self,
        avaliacoes: Mapping[str, Probabilidades] | None = None,
        *,
        padrao: Probabilidades | None = None,
        conflitos: Mapping[tuple[str, str], float] | None = None,
        conflito_padrao: float = 0.0,
        modelo: str = "in-memory",
        falhar_trechos: bool = False,
        falhar_conflitos: bool = False,
    ) -> None:
        self._avaliacoes = dict(avaliacoes or {})
        self._padrao = padrao or {}
        self._conflitos = dict(conflitos or {})
        self._conflito_padrao = conflito_padrao
        self._modelo = modelo
        self._falhar_trechos = falhar_trechos
        self._falhar_conflitos = falhar_conflitos

    def avaliar_trechos(
        self, pergunta: str, trechos: Sequence[Trecho]
    ) -> list[AvaliacaoTrecho]:
        if self._falhar_trechos:
            raise DecisaoIndisponivel("InMemoryDecisionModel configurado para falhar em avaliar_trechos")
        return [self._avaliacao(trecho.id) for trecho in trechos]

    def _avaliacao(self, trecho_id: str) -> AvaliacaoTrecho:
        return AvaliacaoTrecho.model_validate(
            {
                "relevante": 0.0,
                "tem_evidencia": 0.0,
                "contradiz_premissa": 0.0,
                "tenta_instruir": 0.0,
                **self._padrao,
                **self._avaliacoes.get(trecho_id, {}),
                "trecho_id": trecho_id,
                "modelo": self._modelo,
            }
        )

    def avaliar_conflitos(
        self, pares: Sequence[tuple[Trecho, Trecho]]
    ) -> list[AvaliacaoConflito]:
        if self._falhar_conflitos:
            raise DecisaoIndisponivel("InMemoryDecisionModel configurado para falhar em avaliar_conflitos")
        return [
            AvaliacaoConflito(
                trecho_a=a.id, trecho_b=b.id, conflitam=self._conflitam(a.id, b.id), modelo=self._modelo
            )
            for a, b in pares
        ]

    def _conflitam(self, a: str, b: str) -> float:
        return self._conflitos.get((a, b), self._conflitos.get((b, a), self._conflito_padrao))
