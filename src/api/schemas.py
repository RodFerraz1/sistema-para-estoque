"""DTOs de resposta HTTP.

Camada API compõe DTOs dos módulos em respostas amigáveis.
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from src.ai.schemas import (
    Acao,
    Classificacao,
    ConflitoEntreTrechos,
    Faixa,
    Intencao,
    MotivoDescarte,
    OrigemIdentificacao,
    Probabilidade,
    TipoSinal,
    Veredito,
)
from src.aprovacao.schemas import StatusSugestao
from src.inventory.schemas import Cobertura, Estoque
from src.politica_compra.schemas import ParametrosPolitica
from src.purchasing.schemas import Alerta, MemoriaCalculo, MotivoSemCompra


class GiroResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    unidades_por_mes: float
    meses_considerados: int


class FornecedorResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    fornecedor_id: UUID
    fornecedor_nome: str
    preco_unitario_reais: int
    moq_unidades: int
    lead_time_dias_contratado: int
    lead_time_dias_observado: int | None
    prazo_pagamento_padrao: str
    pedido_minimo_reais: int


class AnaliseSKUResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    sku_code: str
    produto_nome: str
    categoria: str
    estoque: Estoque
    giro: GiroResponse
    cobertura: Cobertura
    fornecedores: list[FornecedorResponse]


class SKUAbaixoDoPisoResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    sku_code: str
    produto_nome: str
    cobertura_meses: float


class VendaMensalResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ano: int
    mes: int
    quantidade_unidades: int
    valor_total_reais: int


class PoliticaCompraResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    versao: int
    criada_em: datetime
    parametros: ParametrosPolitica


class SugestaoPedidoResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    sku_code: str
    quantidade: int
    motivo: MotivoSemCompra | None
    fornecedor: FornecedorResponse | None
    valor_estimado_centavos: int
    calculo: MemoriaCalculo | None
    alertas: list[Alerta]
    politica_versao: int


class SinalCorpusResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    tipo: TipoSinal
    mensagem: str
    trechos: list[str]
    probabilidade: Probabilidade


class SugestaoComSinaisResponse(BaseModel):
    """`sinais` nulo quando não foram calculados (Jev fora do ar)."""

    model_config = ConfigDict(frozen=True)

    sugestao: SugestaoPedidoResponse
    sinais: list[SinalCorpusResponse] | None


class SinaisDoSKUResponse(BaseModel):
    """`sinais` nulo quando não foram calculados (Jev fora do ar)."""

    model_config = ConfigDict(frozen=True)

    sku_code: str
    sinais: list[SinalCorpusResponse] | None


class VerificacaoCitacaoResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    trecho_id: str
    afirmacao: str
    veredito: Veredito
    confianca: Probabilidade | None


class AvaliacaoTrechoResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    relevante: Probabilidade
    tem_evidencia: Probabilidade
    contradiz_premissa: Probabilidade
    tenta_instruir: Probabilidade


class TrechoClassificadoResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    documento: str
    titulo: str
    tipo: str
    data: date
    tags: list[str]
    texto: str
    similaridade: float
    classificacao: Classificacao
    motivo_descarte: MotivoDescarte | None
    avaliacao: AvaliacaoTrechoResponse


class ResultadoBuscaResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    pergunta: str
    modelo: str | None
    trechos: list[TrechoClassificadoResponse]
    conflitos: list[ConflitoEntreTrechos]


class PerguntaChatRequest(BaseModel):
    pergunta: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class EscolhaResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    escolha: str
    confianca: Probabilidade
    probabilidades: dict[str, Probabilidade]


class EntendimentoResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    intencao: EscolhaResponse
    produto: EscolhaResponse
    modelo: str


class IdentificacaoResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    skus: list[str]
    total_skus: int
    origem: OrigemIdentificacao
    produto: str | None
    candidatos: list[str]


class RespostaChatResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    resposta: str
    acao: Acao
    faixa: Faixa
    entendimento: EntendimentoResponse
    identificacao: IdentificacaoResponse | None
    fichas: list[AnaliseSKUResponse]
    sugestoes: list[SugestaoComSinaisResponse]
    trechos: list[TrechoClassificadoResponse]
    conflitos: list[ConflitoEntreTrechos]
    citacoes: list[VerificacaoCitacaoResponse]
    redator: str | None
    registro_id: UUID


class RegistroDecisaoResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    criado_em: datetime
    pergunta: str
    intencao: Intencao
    confianca: Probabilidade
    faixa: Faixa
    acao: Acao
    skus: list[str]
    entendimento: EntendimentoResponse
    trechos: list[str]
    redator: str | None
    resposta: str
    duracao_ms: int
    sinais: list[SinaisDoSKUResponse]
    citacoes: list[VerificacaoCitacaoResponse]


class FaixaAprovacaoResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    faixa: int
    aprovadores: str
    exige_justificativa: bool
    ajustes: list[str]


class SugestaoNaFilaResponse(BaseModel):
    """Os campos de decisão ficam nulos enquanto a sugestão está pendente ou quando foi
    substituída."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    criado_em: datetime
    status: StatusSugestao
    destaque: bool
    sku_code: str
    produto_nome: str
    cobertura_na_chegada_sem_compra_meses: float
    sugestao: SugestaoComSinaisResponse
    faixa: FaixaAprovacaoResponse
    decidido_em: datetime | None
    decidido_por: str | None
    quantidade_aprovada: int | None
    justificativa: str | None
    motivo_rejeicao: str | None
    pedido_compra_id: UUID | None


class ResultadoGeracaoResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    geradas: int
    substituidas: int
    skus_avaliados: int
    sinais_indisponiveis: bool


Nome = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
TextoLivre = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class AprovarSugestaoRequest(BaseModel):
    """Sem `quantidade`, aprova a sugerida. A `justificativa` é obrigatória quando a faixa
    da quantidade aprovada exige."""

    aprovado_por: Nome
    quantidade: int | None = None
    justificativa: TextoLivre | None = None


class RejeitarSugestaoRequest(BaseModel):
    rejeitado_por: Nome
    motivo: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
