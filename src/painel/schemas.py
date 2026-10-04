"""DTOs de domínio do módulo `painel`."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.catalog.schemas import SKU
from src.politica_compra.schemas import MotivoAlerta

TipoAviso = Literal["acabou", "vendendo_muito"]
TipoDecisao = Literal["vou_comprar", "negociando", "nao_comprar_agora"]


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
    para o mais antigo."""

    model_config = ConfigDict(frozen=True)

    sku: SKU
    disponivel: int
    cobertura_atual_meses: float | None
    cobertura_na_chegada_sem_compra_meses: float | None
    motivos: list[MotivoAlerta]
    quantidade_sugerida: int | None
    fornecedor_sugerido: str | None
    avisos_abertos: list[Aviso]

    @property
    def so_por_aviso(self) -> bool:
        """No painel só pelo aviso: o cálculo não vê motivo de alerta."""
        return bool(self.avisos_abertos) and not self.motivos


class ItemDecidido(BaseModel):
    """SKU com decisão de compra vigente: fica fora dos alertas até ela vencer ou chegar
    um aviso novo."""

    model_config = ConfigDict(frozen=True)

    sku: SKU
    decisao: DecisaoCompra


class PainelDeAlertas(BaseModel):
    """`skus_com_erro` lista os SKUs que o painel pulou por dado quebrado no ERP (sem a
    linha de estoque)."""

    model_config = ConfigDict(frozen=True)

    alertas: list[ItemAlerta]
    decididos: list[ItemDecidido]
    skus_com_erro: list[str]
