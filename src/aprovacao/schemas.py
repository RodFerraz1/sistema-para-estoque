"""DTOs de domínio do módulo `aprovacao`."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from src.ai.schemas import SugestaoComSinais
from src.catalog.schemas import SKU
from src.purchasing.schemas import FaixaAprovacao

StatusSugestao = Literal["pendente", "aprovada", "rejeitada", "substituida"]


class SugestaoNaFila(BaseModel):
    """Sugestão de pedido guardada na fila de aprovação, com os sinais do corpus e a
    faixa de aprovação. Só entra na fila sugestão com compra (quantidade, fornecedor
    e cálculo). Na aprovação, `faixa` passa a ser a recalculada com a
    quantidade aprovada e a política em vigor. Os campos de decisão ficam nulos
    enquanto a sugestão está pendente ou quando foi substituída."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    criado_em: datetime
    status: StatusSugestao
    destaque: bool
    sku: SKU
    sugestao: SugestaoComSinais
    faixa: FaixaAprovacao
    decidido_em: datetime | None = None
    decidido_por: str | None = None
    quantidade_aprovada: int | None = None
    justificativa: str | None = None
    motivo_rejeicao: str | None = None
    pedido_compra_id: UUID | None = None

    @model_validator(mode="after")
    def _com_compra(self) -> Self:
        sugestao = self.sugestao.sugestao
        if sugestao.quantidade <= 0 or sugestao.fornecedor is None or sugestao.calculo is None:
            raise ValueError(f"a sugestão de '{sugestao.sku_code}' não tem compra")
        if sugestao.sku_code != self.sku.sku_code:
            raise ValueError(f"a sugestão é de '{sugestao.sku_code}' e o SKU é '{self.sku.sku_code}'")
        return self

    @property
    def sku_code(self) -> str:
        return self.sku.sku_code

    @property
    def cobertura_na_chegada_sem_compra_meses(self) -> float:
        calculo = self.sugestao.sugestao.calculo
        assert calculo is not None
        return calculo.cobertura_na_chegada_sem_compra_meses


class ResultadoGeracao(BaseModel):
    """`substituidas` conta as pendentes anteriores que saíram da fila.
    `sinais_indisponiveis` diz que o modelo de decisão caiu e as sugestões entraram
    sem sinais."""

    model_config = ConfigDict(frozen=True)

    geradas: int
    substituidas: int
    skus_avaliados: int
    sinais_indisponiveis: bool
