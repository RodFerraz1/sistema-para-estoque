"""Busca no corpus com o filtro do Jev (ADR-0002): o Jev responde, o código classifica."""
from __future__ import annotations

from dataclasses import dataclass

from src.ai.decisao import DecisionModel
from src.ai.embeddings import Embedder
from src.ai.repositorio import TrechosRepositorio
from src.ai.schemas import (
    AvaliacaoTrecho,
    Classificacao,
    MotivoDescarte,
    ResultadoBusca,
    TrechoClassificado,
    TrechoRecuperado,
)

K_PADRAO = 30


@dataclass(frozen=True)
class Limiares:
    """Calibrados no spike com o jev-1.13.0 e as perguntas em PT (`.scratch/rag-jev/spike-resultado.md`)."""

    injecao: float
    contradiz_premissa: float
    relevante: float
    evidencia: float


LIMIARES = Limiares(injecao=0.50, contradiz_premissa=0.85, relevante=0.55, evidencia=0.15)

_ORDEM: dict[Classificacao, int] = {"aceito": 0, "conflitante": 1, "descartado": 2}


class BuscaContexto:
    def __init__(
        self, embedder: Embedder, repositorio: TrechosRepositorio, decisao: DecisionModel
    ) -> None:
        self._embedder = embedder
        self._repositorio = repositorio
        self._decisao = decisao

    def buscar(self, pergunta: str, k: int = K_PADRAO) -> ResultadoBusca:
        [vetor] = self._embedder.embed([pergunta])
        recuperados = self._repositorio.buscar_similares(vetor, k)
        if not recuperados:
            return ResultadoBusca(pergunta=pergunta, modelo=None, trechos=[], conflitos=[])
        avaliacoes = {a.trecho_id: a for a in self._decisao.avaliar_trechos(pergunta, recuperados)}
        trechos = sorted(
            (_classificar(trecho, avaliacoes[trecho.id]) for trecho in recuperados),
            key=lambda t: (_ORDEM[t.classificacao], -t.similaridade),
        )
        return ResultadoBusca(
            pergunta=pergunta,
            modelo=avaliacoes[recuperados[0].id].modelo,
            trechos=trechos,
            conflitos=[],
        )


def _classificar(trecho: TrechoRecuperado, avaliacao: AvaliacaoTrecho) -> TrechoClassificado:
    classificacao, motivo = _regras(avaliacao)
    return TrechoClassificado(
        **trecho.model_dump(),
        classificacao=classificacao,
        motivo_descarte=motivo,
        avaliacao=avaliacao,
    )


def _regras(avaliacao: AvaliacaoTrecho) -> tuple[Classificacao, MotivoDescarte | None]:
    if avaliacao.tenta_instruir > LIMIARES.injecao:
        return "descartado", "injecao"
    if avaliacao.contradiz_premissa > LIMIARES.contradiz_premissa:
        return "conflitante", None
    if avaliacao.relevante < LIMIARES.relevante:
        return "descartado", "irrelevante"
    if avaliacao.tem_evidencia > LIMIARES.evidencia:
        return "aceito", None
    return "descartado", "sem_evidencia"
