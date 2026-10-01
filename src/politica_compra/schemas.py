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


class MotivoDestaque(StrEnum):
    """Alertas do `purchasing` e sinais do corpus que o comprador pode escolher para pôr
    uma sugestão em destaque na fila de aprovação. Os valores são os de `TipoAlerta` e
    de `TipoSinal`, que ficam em módulos acima deste."""

    RUPTURA_ANTES_DA_CHEGADA = "ruptura_antes_da_chegada"
    VIOLA_TETO = "viola_teto"
    LEAD_TIME_OBSERVADO_ACIMA_DO_CONTRATADO = "lead_time_observado_acima_do_contratado"
    ABAIXO_PEDIDO_MINIMO = "abaixo_pedido_minimo"
    PERIODO_SAZONAL = "periodo_sazonal"
    ATRASO_DO_FORNECEDOR = "atraso_do_fornecedor"
    DEMANDA_SAZONAL = "demanda_sazonal"
    ENCALHE = "encalhe"


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
    faixa_1_ate_reais: int = Field(gt=0)
    faixa_2_ate_reais: int
    faixa_3_ate_reais: int
    motivos_de_destaque: tuple[MotivoDestaque, ...]

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
        if len(set(self.motivos_de_destaque)) != len(self.motivos_de_destaque):
            raise ValueError("motivos_de_destaque não pode ter motivo repetido")
        if not self.faixa_1_ate_reais < self.faixa_2_ate_reais < self.faixa_3_ate_reais:
            raise ValueError(
                "os limites das faixas precisam crescer: "
                "faixa_1_ate_reais < faixa_2_ate_reais < faixa_3_ate_reais"
            )
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
    faixa_1_ate_reais=15_000,
    faixa_2_ate_reais=60_000,
    faixa_3_ate_reais=150_000,
    motivos_de_destaque=(MotivoDestaque.RUPTURA_ANTES_DA_CHEGADA, MotivoDestaque.VIOLA_TETO),
)


class PoliticaCompra(BaseModel):
    model_config = ConfigDict(frozen=True)

    versao: int
    criada_em: datetime
    parametros: ParametrosPolitica
