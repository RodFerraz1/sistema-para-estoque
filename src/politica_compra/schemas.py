"""DTOs de domínio do módulo `politica_compra`.

Os parâmetros são um conjunto fechado (ADR-0003): campo novo exige
migration e valor padrão, nunca chave livre.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

DIAS_POR_MES = 30


class LeadTimeBase(StrEnum):
    OBSERVADO = "observado"
    CONTRATADO = "contratado"
    MAIOR = "maior"


class CriterioFornecedor(StrEnum):
    MENOR_PRECO = "menor_preco"
    MENOR_LEAD_TIME = "menor_lead_time"


class SazonalidadeModo(StrEnum):
    IGNORAR = "ignorar"
    ALERTAR = "alertar"


Mes = Annotated[int, Field(ge=1, le=12)]


class ParametrosPolitica(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    teto_meses: float = Field(gt=0)
    piso_alerta_dias: int = Field(ge=1)
    piso_reposicao_dias: int
    ciclo_compra_meses: float = Field(gt=0)
    lead_time_base: LeadTimeBase
    criterio_fornecedor: CriterioFornecedor
    sazonalidade_modo: SazonalidadeModo
    meses_quentes: tuple[Mes, ...]
    extra_sazonal_meses: float = Field(ge=0)
    dias_historico_minimo: int = Field(ge=0)

    @model_validator(mode="after")
    def _regras_entre_campos(self) -> Self:
        if self.piso_alerta_dias > self.piso_reposicao_dias:
            raise ValueError("piso_alerta_dias não pode passar de piso_reposicao_dias")
        # Senão toda compra que atinge piso + ciclo já nasceria violando o teto.
        if self.piso_reposicao_dias / DIAS_POR_MES + self.ciclo_compra_meses > self.teto_meses:
            raise ValueError(
                "piso_reposicao_dias / 30 + ciclo_compra_meses não pode passar de teto_meses"
            )
        if len(set(self.meses_quentes)) != len(self.meses_quentes):
            raise ValueError("meses_quentes não pode ter mês repetido")
        return self


PARAMETROS_V1 = ParametrosPolitica(
    teto_meses=3.0,
    piso_alerta_dias=20,
    piso_reposicao_dias=30,
    ciclo_compra_meses=1.0,
    lead_time_base=LeadTimeBase.OBSERVADO,
    criterio_fornecedor=CriterioFornecedor.MENOR_PRECO,
    sazonalidade_modo=SazonalidadeModo.ALERTAR,
    meses_quentes=(5, 6, 11, 12),
    extra_sazonal_meses=2.0,
    dias_historico_minimo=60,
)


class PoliticaCompra(BaseModel):
    model_config = ConfigDict(frozen=True)

    versao: int
    criada_em: datetime
    parametros: ParametrosPolitica
