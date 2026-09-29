"""Adapters em memória do módulo `ai`, para testes e para medir o recall sem banco."""
from __future__ import annotations

import hashlib
import math
import re

from src.ai.embeddings import DIMENSAO
from src.ai.repositorio import TrechosRepositorio
from src.ai.schemas import TrechoIndexado, TrechoRecuperado


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
