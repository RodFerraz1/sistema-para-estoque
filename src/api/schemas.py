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
from src.erp_adapter.schemas import StatusPedidoCompra
from src.inventory.schemas import Cobertura, Estoque, StatusEmTransito
from src.painel.schemas import GrupoDoPainel, TipoAviso, TipoDecisao
from src.politica_compra.schemas import MotivoAlerta, ParametrosPolitica
from src.purchasing.schemas import Alerta, MemoriaCalculo, MotivoSemCompra
from src.usuarios.schemas import Papel

TextoLivre = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


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
    """`em_transito_unidades` soma o que ainda falta chegar dos pedidos de compra abertos."""

    model_config = ConfigDict(frozen=True)

    sku_code: str
    produto_nome: str
    categoria: str
    cor: str
    tamanho: str
    estoque: Estoque
    em_transito_unidades: int
    giro: GiroResponse
    cobertura: Cobertura
    fornecedores: list[FornecedorResponse]


class SKUAbaixoDoPisoResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    sku_code: str
    produto_nome: str
    cobertura_meses: float
    cobertura_dias: float


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
    """`sku_code`: o SKU da tela de onde o comprador pergunta, se houver."""

    pergunta: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    sku_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None = None


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
    sku_em_contexto: str | None



class PrecoPagoResponse(BaseModel):
    """Preço unitário pago num pedido de compra, em centavos. `data` é a data do pedido."""

    model_config = ConfigDict(frozen=True)

    data: datetime
    fornecedor_nome: str
    preco_unitario_centavos: int
    quantidade: int
    status: StatusPedidoCompra


class SubstitutoResponse(BaseModel):
    """O menor preço atual entre os fornecedores do substituto, em centavos."""

    model_config = ConfigDict(frozen=True)

    sku_code: str
    produto_nome: str
    cor: str
    tamanho: str
    preco_unitario_centavos: int
    fornecedor_nome: str


class PrecosResponse(BaseModel):
    """`historico` do pedido mais recente para o mais antigo, sem os cancelados;
    `precos_atuais` do fornecedor mais barato ao mais caro; até 10 `substitutos`, pelo preço."""

    model_config = ConfigDict(frozen=True)

    historico: list[PrecoPagoResponse]
    precos_atuais: list[FornecedorResponse]
    substitutos: list[SubstitutoResponse]


class SKUResumoResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    sku_code: str
    produto_nome: str
    cor: str
    tamanho: str


class AvisoResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    sku_code: str
    tipo: TipoAviso
    comentario: str | None
    avisado_por: str
    criado_em: datetime


class RegistrarAvisoRequest(BaseModel):
    sku_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    tipo: TipoAviso
    comentario: TextoLivre | None = None


class ItemAlertaResponse(BaseModel):
    """A cobertura vem em meses e em dias. A atual é nula para SKU sem giro; a na chegada sem
    a compra, nula quando a sugestão não tem cálculo. Quantidade e fornecedor só com compra.
    `so_por_aviso`: tem aviso aberto e nenhum motivo de alerta calculado."""

    model_config = ConfigDict(frozen=True)

    sku_code: str
    produto_nome: str
    cor: str
    tamanho: str
    disponivel: int
    cobertura_atual_meses: float | None
    cobertura_atual_dias: float | None
    cobertura_na_chegada_sem_compra_meses: float | None
    cobertura_na_chegada_sem_compra_dias: float | None
    motivos: list[MotivoAlerta]
    quantidade_sugerida: int | None
    fornecedor_sugerido: str | None
    avisos_abertos: int
    ultimo_aviso: AvisoResponse | None
    so_por_aviso: bool
    grupo: GrupoDoPainel


class DecisaoCompraResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    sku_code: str
    tipo: TipoDecisao
    quantidade: int | None
    motivo: str | None
    comentario: str | None
    decidido_por: str
    quantidade_sugerida: int
    politica_versao: int
    criado_em: datetime


class RegistrarDecisaoRequest(BaseModel):
    """`quantidade` só em `vou_comprar`, maior que zero; `motivo` obrigatório em
    `nao_comprar_agora`."""

    tipo: TipoDecisao
    quantidade: int | None = None
    motivo: TextoLivre | None = None
    comentario: TextoLivre | None = None


class ItemDecididoResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    sku_code: str
    produto_nome: str
    cor: str
    tamanho: str
    decisao: DecisaoCompraResponse


class CobrancaEntregaResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    pedido_id: UUID
    fornecedor_id: UUID
    nova_previsao: date | None
    comentario: str | None
    cobrado_por: str
    criado_em: datetime


class RegistrarCobrancaRequest(BaseModel):
    """`nova_previsao` opcional, de hoje em diante."""

    nova_previsao: date | None = None
    comentario: TextoLivre | None = None


class SKUComEntregaAtrasadaResponse(BaseModel):
    """`cobertura_dias` é nula para SKU sem giro."""

    model_config = ConfigDict(frozen=True)

    sku_code: str
    produto_nome: str
    cor: str
    tamanho: str
    quantidade_pendente: int
    disponivel: int
    cobertura_dias: float | None
    em_ruptura: bool


class PedidoAtrasadoResponse(BaseModel):
    """`ultima_cobranca`: a cobrança que venceu sem a mercadoria chegar, se houve."""

    model_config = ConfigDict(frozen=True)

    pedido_id: UUID
    status: StatusEmTransito
    data_prevista_entrega: date
    dias_de_atraso: int
    ultima_cobranca: CobrancaEntregaResponse | None
    skus: list[SKUComEntregaAtrasadaResponse]


class FornecedorComAtrasoResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    fornecedor_id: UUID
    fornecedor_nome: str
    tem_sku_em_ruptura: bool
    maior_atraso_dias: int
    pedidos: list[PedidoAtrasadoResponse]


class EntregaPendenteResponse(BaseModel):
    """`dias_de_atraso` só quando a data prevista já passou. `cobrancas`: da mais recente
    para a mais antiga; a nova previsão é a da primeira."""

    model_config = ConfigDict(frozen=True)

    pedido_id: UUID
    fornecedor_nome: str
    status: StatusEmTransito
    quantidade_pendente: int
    data_prevista_entrega: date | None
    atrasada: bool
    dias_de_atraso: int | None
    cobranca_vigente: bool
    cobrancas: list[CobrancaEntregaResponse]


class AtrasoRecebidoResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    pedido_id: UUID
    data_prevista_entrega: date
    recebido_em: datetime
    dias_de_atraso: int


class HistoricoDeAtrasosResponse(BaseModel):
    """`media_dias_de_atraso` é só das entregas atrasadas, nula sem nenhuma. `atrasos`: do
    recebimento mais recente para o mais antigo."""

    model_config = ConfigDict(frozen=True)

    fornecedor_id: UUID
    fornecedor_nome: str
    entregas_recebidas: int
    entregas_atrasadas: int
    media_dias_de_atraso: float | None
    atrasos: list[AtrasoRecebidoResponse]


class PainelResponse(BaseModel):
    """`decididos`: os SKUs com decisão de compra vigente, a mais recente primeiro.
    `contagens`: quantos alertas cada grupo tem, com o filtro aplicado.
    `entregas_atrasadas`: os pedidos atrasados sem cobrança vigente dos SKUs dos alertas,
    por fornecedor, primeiro os que têm SKU em ruptura e depois o maior atraso."""

    model_config = ConfigDict(frozen=True)

    alertas: list[ItemAlertaResponse]
    decididos: list[ItemDecididoResponse]
    skus_com_erro: list[str]
    contagens: dict[GrupoDoPainel, int]
    entregas_atrasadas: list[FornecedorComAtrasoResponse]


class ItemEstoqueResponse(BaseModel):
    """`cobertura_dias` é nula para SKU sem giro."""

    model_config = ConfigDict(frozen=True)

    sku_code: str
    produto_nome: str
    cor: str
    tamanho: str
    categoria: str
    disponivel: int
    em_transito: int
    venda_media_diaria: float
    cobertura_dias: float | None
    em_ruptura: bool


class EstoqueResponse(BaseModel):
    """`total` conta os SKUs de todas as páginas com o filtro aplicado."""

    model_config = ConfigDict(frozen=True)

    itens: list[ItemEstoqueResponse]
    total: int
    pagina: int
    por_pagina: int


class FornecedorResumoResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    nome: str


class LoginRequest(BaseModel):
    email: Annotated[str, StringConstraints(max_length=320)]
    senha: Annotated[str, StringConstraints(max_length=200)]


class UsuarioResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    nome: str
    email: str
    papeis: list[Papel]


Senha = Annotated[str, StringConstraints(max_length=200)]


class UsuarioAdminResponse(BaseModel):
    """A pessoa como o admin vê na lista: papéis, situação e último acesso (nulo para
    quem nunca entrou)."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    nome: str
    email: str
    papeis: list[Papel]
    ativo: bool
    criado_em: datetime
    ultimo_acesso_em: datetime | None


class CriarUsuarioRequest(BaseModel):
    nome: Annotated[str, StringConstraints(max_length=200)]
    email: Annotated[str, StringConstraints(max_length=320)]
    senha: Senha
    papeis: list[Papel]


class PapeisRequest(BaseModel):
    papeis: list[Papel]


class RedefinirSenhaRequest(BaseModel):
    senha: Senha


class TrocarSenhaRequest(BaseModel):
    senha_atual: Senha
    nova_senha: Senha
