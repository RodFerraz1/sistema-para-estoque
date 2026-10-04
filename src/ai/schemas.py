"""DTOs de domínio do módulo `ai`."""
from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.catalog.schemas import SKU
from src.ficha_sku.schemas import Ficha
from src.painel.schemas import ItemAlerta
from src.politica_compra.schemas import PoliticaCompra
from src.purchasing.schemas import SugestaoPedido

Classificacao = Literal["aceito", "conflitante", "descartado"]
MotivoDescarte = Literal["injecao", "irrelevante", "sem_evidencia"]
Probabilidade = Annotated[float, Field(ge=0, le=1)]
Intencao = Literal["situacao_sku", "sugestao_compra", "politica_ou_fornecedor", "alertas_e_avisos", "fora_de_escopo"]
Faixa = Literal["alta", "media", "baixa"]
Acao = Literal["respondeu", "confirmou_e_respondeu", "pediu_esclarecimento", "fora_de_escopo"]
OrigemIdentificacao = Literal["codigo", "produto", "contexto", "nenhum"]
TipoSinal = Literal["atraso_do_fornecedor", "demanda_sazonal", "encalhe"]
Relacao = Literal["sustenta", "contradiz", "nao_trata"]
Veredito = Literal["confirmada", "sem_suporte", "contradita", "inventada", "incerta"]
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
    em `MAX_SKUS_POR_RESPOSTA`. Origem `contexto`: a pergunta não citou produto e vale o
    SKU da tela de onde o comprador perguntou."""

    model_config = ConfigDict(frozen=True)

    skus: list[str]
    total_skus: int
    origem: OrigemIdentificacao
    produto: str | None
    candidatos: list[str]


class ProdutoDoSinal(BaseModel):
    model_config = ConfigDict(frozen=True)

    nome: str
    categoria: str


class AvaliacaoSinais(BaseModel):
    """Probabilidades que o modelo de decisão deu para um trecho relatar cada tipo de
    sinal sobre o fornecedor e o produto de uma sugestão, uma por `TipoSinal`."""

    model_config = ConfigDict(frozen=True)

    trecho_id: str
    probabilidades: dict[TipoSinal, Probabilidade]
    modelo: str

    @field_validator("probabilidades")
    @classmethod
    def _um_por_tipo(cls, probabilidades: dict[TipoSinal, float]) -> dict[TipoSinal, float]:
        if faltando := set(get_args(TipoSinal)) - probabilidades.keys():
            raise ValueError(f"sem probabilidade para {sorted(faltando)}")
        return probabilidades


class SinalCorpus(BaseModel):
    """O que o corpus relata sobre o fornecedor ou o produto de uma sugestão.
    `trechos` são os ids de origem, do mais provável ao menos provável, e
    `probabilidade` é a maior entre eles. Nunca altera a quantidade sugerida."""

    model_config = ConfigDict(frozen=True)

    tipo: TipoSinal
    mensagem: str
    trechos: list[str]
    probabilidade: Probabilidade


class SugestaoComSinais(BaseModel):
    """`sinais` é nulo quando não foram calculados (modelo de decisão fora do ar) e
    lista vazia quando foram calculados sem nenhum sinal ou a sugestão não tem
    fornecedor."""

    model_config = ConfigDict(frozen=True)

    sugestao: SugestaoPedido
    sinais: list[SinalCorpus] | None


class SinaisDasSugestoes(BaseModel):
    """Sinais por `sku_code`, um item por sugestão, e os trechos que deram origem a
    algum deles, sem repetição, na ordem em que aparecem nos sinais."""

    model_config = ConfigDict(frozen=True)

    por_sku: dict[str, list[SinalCorpus]]
    trechos_de_origem: list[TrechoClassificado]


class SinaisDoSKU(BaseModel):
    """`sinais` nulo quando não foram calculados, como em `SugestaoComSinais`."""

    model_config = ConfigDict(frozen=True)

    sku_code: str
    sinais: list[SinalCorpus] | None


class Citacao(BaseModel):
    """Um id de trecho citado entre colchetes num texto redigido, com a frase que o cita
    (`afirmacao`, sem as citações)."""

    model_config = ConfigDict(frozen=True)

    trecho_id: str
    afirmacao: str


class AvaliacaoCitacao(BaseModel):
    """Resposta do modelo de decisão sobre como o trecho se relaciona com a afirmação."""

    model_config = ConfigDict(frozen=True)

    afirmacao: str
    trecho_id: str
    escolha: Relacao
    confianca: Probabilidade
    probabilidades: dict[str, Probabilidade]
    modelo: str


class VerificacaoCitacao(BaseModel):
    """Veredito do código sobre uma citação. `confianca` é a do modelo de decisão e fica
    nula quando ele não foi consultado (`inventada`, ou `incerta` sem avaliação)."""

    model_config = ConfigDict(frozen=True)

    trecho_id: str
    afirmacao: str
    veredito: Veredito
    confianca: Probabilidade | None


class CitacoesConferidas(BaseModel):
    """O texto com as citações não confirmadas marcadas e a verificação de cada uma.
    `decisao_indisponivel` diz que o modelo de decisão caiu e as citações do contexto
    ficaram `incerta` sem ser avaliadas."""

    model_config = ConfigDict(frozen=True)

    texto: str
    verificacoes: list[VerificacaoCitacao]
    decisao_indisponivel: bool


class Montagem(BaseModel):
    """Dados que o código reuniu para responder uma pergunta do chat. `alertas` são os
    itens do painel de alertas, na ordem dele."""

    model_config = ConfigDict(frozen=True)

    fichas: list[Ficha] = []
    sugestoes: list[SugestaoComSinais] = []
    alertas: list[ItemAlerta] = []
    politica: PoliticaCompra | None = None
    trechos: list[TrechoClassificado] = []
    conflitos: list[ConflitoEntreTrechos] = []
    observacoes: list[str] = []


class RespostaCopilot(BaseModel):
    """`trechos` são os que foram ao redator. `redator` é nulo quando a resposta é
    feita em código (esclarecimento ou fora de escopo). `citacoes` só vêm de
    resposta redigida por LLM."""

    model_config = ConfigDict(frozen=True)

    resposta: str
    acao: Acao
    faixa: Faixa
    entendimento: Entendimento
    identificacao: Identificacao | None
    fichas: list[Ficha]
    sugestoes: list[SugestaoComSinais]
    trechos: list[TrechoClassificado]
    conflitos: list[ConflitoEntreTrechos]
    citacoes: list[VerificacaoCitacao]
    redator: str | None
    registro_id: UUID


class RegistroDecisao(BaseModel):
    """O que fica gravado de cada pergunta respondida pelo chat. `intencao` e
    `confianca` repetem o `entendimento` para o M8 filtrar sem abrir o jsonb.
    `trechos` são os ids que foram ao redator. `sinais` traz um item por sugestão,
    com `sinais` nulo quando não foram calculados. `sku_em_contexto` é o SKU da tela de
    onde o comprador perguntou, nulo fora da tela do SKU. `usuario_id` é quem perguntou,
    nulo nos registros de antes do login."""

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
    sinais: list[SinaisDoSKU]
    citacoes: list[VerificacaoCitacao]
    sku_em_contexto: str | None = None
    usuario_id: UUID | None = None
