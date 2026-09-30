"""DTOs de domínio do módulo `ai`."""
from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.catalog.schemas import SKU

Classificacao = Literal["aceito", "conflitante", "descartado"]
MotivoDescarte = Literal["injecao", "irrelevante", "sem_evidencia"]
Probabilidade = Annotated[float, Field(ge=0, le=1)]
Intencao = Literal["situacao_sku", "sugestao_compra", "politica_ou_fornecedor", "fora_de_escopo"]
Faixa = Literal["alta", "media", "baixa"]
Acao = Literal["respondeu", "confirmou_e_respondeu", "pediu_esclarecimento", "fora_de_escopo"]
NENHUM_PRODUTO = "nenhum"


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
    """Probabilidades que o modelo de decisão deu para um trecho diante da pergunta."""

    model_config = ConfigDict(frozen=True)

    trecho_id: str
    relevante: Probabilidade
    tem_evidencia: Probabilidade
    contradiz_premissa: Probabilidade
    tenta_instruir: Probabilidade
    modelo: str


class AvaliacaoConflito(BaseModel):
    """Probabilidade que o modelo de decisão deu para os dois trechos afirmarem coisas
    incompatíveis sobre o mesmo fato."""

    model_config = ConfigDict(frozen=True)

    trecho_a: str
    trecho_b: str
    conflitam: Probabilidade
    modelo: str


class TrechoClassificado(TrechoRecuperado):
    classificacao: Classificacao
    motivo_descarte: MotivoDescarte | None
    avaliacao: AvaliacaoTrecho


class ConflitoEntreTrechos(BaseModel):
    model_config = ConfigDict(frozen=True)

    trecho_a: str
    trecho_b: str
    probabilidade: Probabilidade


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


class Escolha[T: str](BaseModel):
    """Resposta de uma `Choice` do modelo de decisão, sem perda."""

    model_config = ConfigDict(frozen=True)

    escolha: T
    confianca: Probabilidade
    probabilidades: dict[str, Probabilidade]


class Entendimento(BaseModel):
    model_config = ConfigDict(frozen=True)

    intencao: Escolha[Intencao]
    produto: Escolha[str]
    modelo: str


class ProdutoCatalogo(BaseModel):
    """Produto do catálogo como opção da pergunta de produto. `nome` é único na lista."""

    model_config = ConfigDict(frozen=True)

    nome: str
    categoria: str
    cores: list[str]
    tamanhos: list[str]
    prefixo: str
    skus: list[SKU]
