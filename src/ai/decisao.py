"""Port do modelo de decisão (o Jev, pela ADR-0002).

O port é de domínio: quem usa recebe probabilidades já nomeadas, e as
perguntas feitas ao modelo ficam dentro do adapter.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from src.ai.schemas import (
    AvaliacaoConflito,
    AvaliacaoSinais,
    AvaliacaoTrecho,
    Entendimento,
    ProdutoCatalogo,
    ProdutoDoSinal,
    Trecho,
)


class DecisaoIndisponivel(Exception):
    pass


class DecisionModel(Protocol):
    def entender_pergunta(
        self, pergunta: str, produtos: Sequence[ProdutoCatalogo]
    ) -> Entendimento: ...

    def avaliar_trechos(
        self, pergunta: str, trechos: Sequence[Trecho]
    ) -> list[AvaliacaoTrecho]: ...

    def avaliar_conflitos(
        self, pares: Sequence[tuple[Trecho, Trecho]]
    ) -> list[AvaliacaoConflito]: ...

    def avaliar_sinais(
        self, fornecedor: str, produto: ProdutoDoSinal, trechos: Sequence[Trecho]
    ) -> list[AvaliacaoSinais]: ...
