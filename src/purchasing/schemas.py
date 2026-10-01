"""DTOs de domínio do módulo `purchasing`."""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from src.catalog.schemas import FornecedorParaSKU
from src.politica_compra.schemas import DIAS_POR_MES


class MotivoSemCompra(StrEnum):
    SKU_NOVO = "sku_novo"
    SEM_GIRO = "sem_giro"
    SEM_FORNECEDOR = "sem_fornecedor"
    ACIMA_DO_PONTO_DE_REPOSICAO = "acima_do_ponto_de_reposicao"


class TipoAlerta(StrEnum):
    RUPTURA_ANTES_DA_CHEGADA = "ruptura_antes_da_chegada"
    VIOLA_TETO = "viola_teto"
    ABAIXO_PEDIDO_MINIMO = "abaixo_pedido_minimo"
    LEAD_TIME_OBSERVADO_ACIMA_DO_CONTRATADO = "lead_time_observado_acima_do_contratado"
    PERIODO_SAZONAL = "periodo_sazonal"


class LeadTimeOrigem(StrEnum):
    OBSERVADO = "observado"
    CONTRATADO = "contratado"


class Alerta(BaseModel):
    model_config = ConfigDict(frozen=True)

    tipo: TipoAlerta
    mensagem: str


class MemoriaCalculo(BaseModel):
    """Números que levaram à quantidade sugerida, em unidades e meses."""

    model_config = ConfigDict(frozen=True)

    giro_mensal: float
    disponivel: int
    em_transito: int
    posicao: int
    lead_time_dias: int
    lead_time_origem: LeadTimeOrigem
    estoque_na_chegada: float
    qtd_necessaria: int
    cobertura_na_chegada_meses: float

    @property
    def cobertura_na_chegada_sem_compra_meses(self) -> float:
        """Cobertura quando a compra chega, sem contar a compra. Negativa quando o
        estoque acaba antes da chegada, ao contrário de `estoque_na_chegada`, que
        para em zero: mede a urgência da compra."""
        consumo_no_lead_time = self.giro_mensal * self.lead_time_dias / DIAS_POR_MES
        return (self.posicao - consumo_no_lead_time) / self.giro_mensal


class SugestaoPedido(BaseModel):
    """Sugestão de compra de um SKU.

    Sempre existe: quando não há o que comprar, `quantidade` é 0 e `motivo`
    diz por quê. `calculo` fica ausente quando o motivo impede o cálculo
    (SKU novo, sem giro, sem fornecedor).
    """

    model_config = ConfigDict(frozen=True)

    sku_code: str
    quantidade: int
    motivo: MotivoSemCompra | None
    fornecedor: FornecedorParaSKU | None
    valor_estimado_centavos: int
    calculo: MemoriaCalculo | None
    alertas: list[Alerta]
    politica_versao: int


class ItemNovoPedido(BaseModel):
    """Item de um pedido de compra que o Copilot cria no ERP."""

    model_config = ConfigDict(frozen=True)

    sku_code: str
    quantidade: int = Field(gt=0)
    preco_unitario_centavos: int = Field(ge=0)


class FaixaAprovacao(BaseModel):
    """Faixa de `politicas/aprovacao-compras.md` de um pedido de compra.

    `ajustes` traz uma frase por exceção do documento que mudou a faixa.
    """

    model_config = ConfigDict(frozen=True)

    faixa: int = Field(ge=1, le=4)
    aprovadores: str
    exige_justificativa: bool
    ajustes: list[str]
