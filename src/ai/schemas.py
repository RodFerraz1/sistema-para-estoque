"""DTOs de domínio do módulo `ai`."""
from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.catalog.schemas import SKU
from src.ficha_sku.schemas import Ficha
from src.politica_compra.schemas import PoliticaCompra
from src.purchasing.schemas import SugestaoPedido

Classificacao = Literal["aceito", "conflitante", "descartado"]
MotivoDescarte = Literal["injecao", "irrelevante", "sem_evidencia"]
Probabilidade = Annotated[float, Field(ge=0, le=1)]
Intencao = Literal["situacao_sku", "sugestao_compra", "politica_ou_fornecedor", "fora_de_escopo"]
Faixa = Literal["alta", "media", "baixa"]
Acao = Literal["respondeu", "confirmou_e_respondeu", "pediu_esclarecimento", "fora_de_escopo"]
OrigemIdentificacao = Literal["codigo", "produto", "nenhum"]
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


class Identificacao(BaseModel):
    """SKUs de uma pergunta do chat. `total_skus` conta os identificados antes do corte
    em `MAX_SKUS_POR_RESPOSTA`."""

    model_config = ConfigDict(frozen=True)

    skus: list[str]
    total_skus: int
    origem: OrigemIdentificacao
    produto: str | None
    candidatos: list[str]


class Montagem(BaseModel):
    """Dados que o código reuniu para responder uma pergunta do chat."""

    model_config = ConfigDict(frozen=True)

    fichas: list[Ficha] = []
    sugestoes: list[SugestaoPedido] = []
    politica: PoliticaCompra | None = None
    trechos: list[TrechoClassificado] = []
    conflitos: list[ConflitoEntreTrechos] = []
    observacoes: list[str] = []


class RespostaCopilot(BaseModel):
    """`trechos` são os que foram ao redator. `redator` é nulo quando a resposta é
    feita em código (esclarecimento ou fora de escopo)."""

    model_config = ConfigDict(frozen=True)

    resposta: str
    acao: Acao
    faixa: Faixa
    entendimento: Entendimento
    identificacao: Identificacao | None
    fichas: list[Ficha]
    sugestoes: list[SugestaoPedido]
    trechos: list[TrechoClassificado]
    conflitos: list[ConflitoEntreTrechos]
    redator: str | None
    registro_id: UUID


class RegistroDecisao(BaseModel):
    """O que fica gravado de cada pergunta respondida pelo chat. `intencao` e
    `confianca` repetem o `entendimento` para o M8 filtrar sem abrir o jsonb.
    `trechos` são os ids que foram ao redator."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    criado_em: datetime
    pergunta: str
    intencao: Intencao
    confianca: Probabilidade
    faixa: Faixa
    acao: Acao
    skus: list[str]
    entendimento: Entendimento
    trechos: list[str]
    redator: str | None
    resposta: str
    duracao_ms: int
