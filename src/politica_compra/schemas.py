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
    """`ignorar` deixa o lead time fora do cálculo: as contas partem da posição de hoje (ADR-0006)."""

    IGNORAR = "ignorar"
    OBSERVADO = "observado"
    CONTRATADO = "contratado"
    MAIOR = "maior"


class CriterioFornecedor(StrEnum):
    MENOR_PRECO = "menor_preco"
    MENOR_LEAD_TIME = "menor_lead_time"


class SazonalidadeModo(StrEnum):
    IGNORAR = "ignorar"
    ALERTAR = "alertar"


class MotivoAlerta(StrEnum):
    """Alertas que o comprador pode escolher para pôr um SKU no painel de alertas. Os
    valores são os de `TipoAlerta`, que fica num módulo acima deste, mais os que o `painel`
    calcula: `abaixo_do_piso_alerta` (cobertura atual abaixo de `piso_alerta_dias`), que o
    comprador chama de ruptura (ADR-0006), e `entrega_atrasada` (pedido de compra com a data
    prevista vencida e sem cobrança vigente)."""

    RUPTURA_ANTES_DA_CHEGADA = "ruptura_antes_da_chegada"
    VIOLA_TETO = "viola_teto"
    LEAD_TIME_OBSERVADO_ACIMA_DO_CONTRATADO = "lead_time_observado_acima_do_contratado"
    ABAIXO_PEDIDO_MINIMO = "abaixo_pedido_minimo"
    PERIODO_SAZONAL = "periodo_sazonal"
    ABAIXO_DO_PISO_ALERTA = "abaixo_do_piso_alerta"
    ENTREGA_ATRASADA = "entrega_atrasada"


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
    motivos_de_alerta: tuple[MotivoAlerta, ...]

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
        if len(set(self.motivos_de_alerta)) != len(self.motivos_de_alerta):
            raise ValueError("motivos_de_alerta não pode ter motivo repetido")
        return self


PARAMETROS_V1 = ParametrosPolitica(
    teto_meses=3.0,
    piso_alerta_dias=20,
    piso_reposicao_dias=30,
    ciclo_compra_meses=2.0,
    lead_time_base=LeadTimeBase.IGNORAR,
    criterio_fornecedor=CriterioFornecedor.MENOR_PRECO,
    sazonalidade_modo=SazonalidadeModo.ALERTAR,
    meses_quentes=(5, 6, 11, 12),
    extra_sazonal_meses=2.0,
    dias_historico_minimo=60,
    motivos_de_alerta=(MotivoAlerta.ABAIXO_DO_PISO_ALERTA, MotivoAlerta.ENTREGA_ATRASADA),
)


class PoliticaCompra(BaseModel):
    model_config = ConfigDict(frozen=True)

    versao: int
    criada_em: datetime
    parametros: ParametrosPolitica
