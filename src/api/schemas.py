"""DTOs de resposta HTTP.

Camada API compõe DTOs dos módulos em respostas amigáveis.
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.ai.identificacao import OrigemIdentificacao
from src.ai.schemas import Acao, Classificacao, ConflitoEntreTrechos, Faixa, Intencao, MotivoDescarte, Probabilidade
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
    pergunta: str = Field(min_length=1, max_length=1000)


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
    sugestoes: list[SugestaoPedidoResponse]
    trechos: list[TrechoClassificadoResponse]
    conflitos: list[ConflitoEntreTrechos]
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
