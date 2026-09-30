"""DTOs de domínio do módulo `ai`."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

Classificacao = Literal["aceito", "conflitante", "descartado"]
MotivoDescarte = Literal["injecao", "irrelevante", "sem_evidencia"]


class Trecho(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    documento: str
    titulo: str
    tipo: str
    data: date
    tags: list[str]
    texto: str


class TrechoIndexado(Trecho):
    embedding: list[float]


class TrechoRecuperado(Trecho):
    similaridade: float


class AvaliacaoTrecho(BaseModel):
    """Probabilidades de 0 a 1 que o modelo de decisão deu para um trecho diante da pergunta."""

    model_config = ConfigDict(frozen=True)

    trecho_id: str
    relevante: float
    tem_evidencia: float
    contradiz_premissa: float
    tenta_instruir: float
    modelo: str


class AvaliacaoConflito(BaseModel):
    """Probabilidade de 0 a 1 que o modelo de decisão deu para os dois trechos se contradizerem."""

    model_config = ConfigDict(frozen=True)

    trecho_a: str
    trecho_b: str
    conflitam: float
    modelo: str


class TrechoClassificado(TrechoRecuperado):
    classificacao: Classificacao
    motivo_descarte: MotivoDescarte | None
    avaliacao: AvaliacaoTrecho


class ConflitoEntreTrechos(BaseModel):
    model_config = ConfigDict(frozen=True)

    trecho_a: str
    trecho_b: str
    probabilidade: float


class ResultadoBusca(BaseModel):
    model_config = ConfigDict(frozen=True)

    pergunta: str
    modelo: str | None
    trechos: list[TrechoClassificado]
    conflitos: list[ConflitoEntreTrechos]


class RelatorioIngestao(BaseModel):
    model_config = ConfigDict(frozen=True)

    novos: list[str]
    alterados: list[str]
    removidos: list[str]
    inalterados: list[str]
    total_trechos: int
