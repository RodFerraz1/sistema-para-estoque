"""DTOs de domínio do módulo `painel`."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.catalog.schemas import SKU
from src.inventory.schemas import StatusEmTransito
from src.politica_compra.schemas import MotivoAlerta

TipoAviso = Literal["acabou", "vendendo_muito"]
TipoDecisao = Literal["vou_comprar", "negociando", "nao_comprar_agora"]
GrupoDoPainel = Literal["pedidos_de_vendas", "entregas_atrasadas", "em_ruptura", "vao_faltar", "outros_alertas"]
GRUPOS: tuple[GrupoDoPainel, ...] = (
    "pedidos_de_vendas",
    "entregas_atrasadas",
    "em_ruptura",
    "vao_faltar",
    "outros_alertas",
)
MotivoDoFiltro = Literal["aviso"] | MotivoAlerta
SituacaoEstoque = Literal["em_ruptura", "sem_venda", "com_transito"]
OrdemEstoque = Literal["cobertura", "venda_diaria", "nome"]
POR_PAGINA_MAXIMO = 100


class Aviso(BaseModel):
    """Recado da equipe de vendas sobre um SKU. Fica aberto até uma decisão de compra
    do mesmo SKU registrada depois dele: não há coluna de status. `avisado_por` é o nome
    de quem avisou no momento; `usuario_id` é nulo nos avisos de antes do login."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    sku_code: str
    tipo: TipoAviso
    comentario: str | None
    avisado_por: str
    usuario_id: UUID | None
    criado_em: datetime


class DecisaoCompra(BaseModel):
    """O que o comprador chefe decidiu sobre um SKU. `quantidade` só em `vou_comprar` e
    `motivo` obrigatório em `nao_comprar_agora`. `quantidade_sugerida` (zero sem compra)
    e `politica_versao` são os da sugestão de pedido no momento da decisão, para comparar
    depois o que o Copilot sugeriu com o que o comprador decidiu. `usuario_id` é nulo nas
    decisões de antes do login."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    sku_code: str
    tipo: TipoDecisao
    quantidade: int | None
    motivo: str | None
    comentario: str | None
    decidido_por: str
    usuario_id: UUID | None
    quantidade_sugerida: int
    politica_versao: int
    criado_em: datetime


class ItemAlerta(BaseModel):
    """SKU no painel de alertas. `cobertura_atual_meses` (só o disponível) é nula para
    SKU sem giro, e `cobertura_na_chegada_sem_compra_meses` quando a sugestão de pedido
    não tem cálculo (SKU novo, sem giro ou sem fornecedor). A quantidade e o fornecedor
    sugeridos só vêm quando a sugestão tem compra. `avisos_abertos` vem do mais recente
    para o mais antigo. `parou_de_vender`: queda de venda com o disponível zero."""

    model_config = ConfigDict(frozen=True)

    sku: SKU
    disponivel: int
    cobertura_atual_meses: float | None
    cobertura_na_chegada_sem_compra_meses: float | None
    motivos: list[MotivoAlerta]
    quantidade_sugerida: int | None
    fornecedor_sugerido: str | None
    avisos_abertos: list[Aviso]
    parou_de_vender: bool = False

    @property
    def so_por_aviso(self) -> bool:
        """No painel só pelo aviso: o cálculo não vê motivo de alerta."""
        return bool(self.avisos_abertos) and not self.motivos

    @property
    def grupo(self) -> GrupoDoPainel:
        """Um grupo só por SKU, o primeiro que couber: aviso aberto, entrega atrasada (já
        comprou e não chegou: o problema é cobrar, não comprar), ruptura, ruptura antes da
        chegada e os outros motivos."""
        if self.avisos_abertos:
            return "pedidos_de_vendas"
        if MotivoAlerta.ENTREGA_ATRASADA in self.motivos:
            return "entregas_atrasadas"
        if MotivoAlerta.ABAIXO_DO_PISO_ALERTA in self.motivos:
            return "em_ruptura"
        if MotivoAlerta.RUPTURA_ANTES_DA_CHEGADA in self.motivos:
            return "vao_faltar"
        return "outros_alertas"


class CobrancaEntrega(BaseModel):
    """O que o comprador chefe registrou depois de cobrar o fornecedor por um pedido de
    compra atrasado. Vale para o pedido inteiro. `cobrado_por` é o nome de quem cobrou no
    momento. A nova previsão vive no Copilot: o ERP não muda (ADR-0005)."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    pedido_id: UUID
    fornecedor_id: UUID
    nova_previsao: date | None
    comentario: str | None
    cobrado_por: str
    usuario_id: UUID
    criado_em: datetime


class SKUComEntregaAtrasada(BaseModel):
    """SKU de um pedido atrasado no painel. `cobertura_meses` é nula para SKU sem giro."""

    model_config = ConfigDict(frozen=True)

    sku: SKU
    quantidade_pendente: int
    disponivel: int
    cobertura_meses: float | None
    em_ruptura: bool


class PedidoAtrasado(BaseModel):
    """Pedido de compra com entrega atrasada e sem cobrança vigente. `ultima_cobranca` é a
    que venceu sem a mercadoria chegar, se houve."""

    model_config = ConfigDict(frozen=True)

    pedido_id: UUID
    status: StatusEmTransito
    data_prevista_entrega: date
    dias_de_atraso: int
    skus: list[SKUComEntregaAtrasada]
    ultima_cobranca: CobrancaEntrega | None


class FornecedorComAtraso(BaseModel):
    """Os pedidos atrasados de um fornecedor, do maior atraso para o menor."""

    model_config = ConfigDict(frozen=True)

    fornecedor_id: UUID
    fornecedor_nome: str
    pedidos: list[PedidoAtrasado]

    @property
    def tem_sku_em_ruptura(self) -> bool:
        return any(s.em_ruptura for p in self.pedidos for s in p.skus)

    @property
    def maior_atraso_dias(self) -> int:
        return max(p.dias_de_atraso for p in self.pedidos)


class EntregaPendente(BaseModel):
    """Item em trânsito de um SKU para a tela do SKU, com as cobranças do pedido da mais
    recente para a mais antiga. `dias_de_atraso` só quando a data prevista já passou."""

    model_config = ConfigDict(frozen=True)

    pedido_id: UUID
    fornecedor_nome: str
    status: StatusEmTransito
    quantidade_pendente: int
    data_prevista_entrega: date | None
    dias_de_atraso: int | None
    cobranca_vigente: bool
    cobrancas: list[CobrancaEntrega]

    @property
    def atrasada(self) -> bool:
        return self.dias_de_atraso is not None


class ItemDecidido(BaseModel):
    """SKU com decisão de compra vigente: fica fora dos alertas até ela vencer ou chegar
    um aviso novo."""

    model_config = ConfigDict(frozen=True)

    sku: SKU
    decisao: DecisaoCompra


class FiltroPainel(BaseModel):
    """Vazio, não filtra. `busca` segue a regra do `catalog.buscar_skus`; `fornecedor_id` é
    de um fornecedor que vende o SKU; `motivo` é um motivo de alerta ou `aviso` (aviso
    aberto da equipe de vendas)."""

    model_config = ConfigDict(frozen=True)

    busca: str | None = None
    categoria: str | None = None
    motivo: MotivoDoFiltro | None = None
    fornecedor_id: UUID | None = None


class PainelDeAlertas(BaseModel):
    """`skus_com_erro` lista os SKUs que o painel pulou por dado quebrado no ERP (sem a
    linha de estoque). `entregas_atrasadas` agrupa por fornecedor os pedidos atrasados dos
    SKUs dos alertas com o motivo `entrega_atrasada`."""

    model_config = ConfigDict(frozen=True)

    alertas: list[ItemAlerta]
    decididos: list[ItemDecidido]
    skus_com_erro: list[str]
    entregas_atrasadas: list[FornecedorComAtraso]

    @property
    def contagens(self) -> dict[GrupoDoPainel, int]:
        """Quantos SKUs dos alertas cada grupo tem, com zero nos vazios."""
        contagens = dict.fromkeys(GRUPOS, 0)
        for item in self.alertas:
            contagens[item.grupo] += 1
        return contagens


class FiltroEstoque(BaseModel):
    """Vazio, não filtra. `busca` segue a regra do `catalog.buscar_skus`; `situacao` é
    `em_ruptura` (cobertura abaixo do piso de alerta), `sem_venda` (sem giro) ou
    `com_transito` (compra a caminho)."""

    model_config = ConfigDict(frozen=True)

    busca: str | None = None
    categoria: str | None = None
    situacao: SituacaoEstoque | None = None


class ItemEstoque(BaseModel):
    """Uma linha da tela de Estoque. `cobertura_meses` é nula para SKU sem giro."""

    model_config = ConfigDict(frozen=True)

    sku: SKU
    disponivel: int
    em_transito: int
    venda_media_diaria: float
    cobertura_meses: float | None
    em_ruptura: bool


class PaginaDeEstoque(BaseModel):
    """`total` conta os SKUs de todas as páginas com o filtro aplicado."""

    model_config = ConfigDict(frozen=True)

    itens: list[ItemEstoque]
    total: int
    pagina: int
    por_pagina: int
