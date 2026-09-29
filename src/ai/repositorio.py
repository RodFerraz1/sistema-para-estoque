"""Port de persistência dos trechos indexados do corpus.

A unidade de escrita é o documento: todos os trechos de um documento são
trocados juntos, e o hash do documento fica gravado em cada trecho. Por
isso documento sem trechos não aparece em `hashes_por_documento`.
"""
from __future__ import annotations

from typing import Protocol

from src.ai.schemas import TrechoIndexado, TrechoRecuperado


class TrechosRepositorio(Protocol):
    def hashes_por_documento(self) -> dict[str, str]: ...

    def substituir_documento(
        self, documento: str, hash_documento: str, trechos: list[TrechoIndexado]
    ) -> None: ...

    def remover_documento(self, documento: str) -> None: ...

    def buscar_similares(self, vetor: list[float], k: int) -> list[TrechoRecuperado]: ...
