"""Port do modelo de decisão (o Jev, pela ADR-0002).

O port é de domínio: quem usa recebe probabilidades já nomeadas, e as
perguntas feitas ao modelo ficam dentro do adapter.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from src.ai.schemas import AvaliacaoTrecho, Trecho


class DecisaoIndisponivel(Exception):
    pass


class DecisionModel(Protocol):
    def avaliar_trechos(
        self, pergunta: str, trechos: Sequence[Trecho]
    ) -> list[AvaliacaoTrecho]: ...
