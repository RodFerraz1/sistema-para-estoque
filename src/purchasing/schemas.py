"""DTOs de domínio do módulo `purchasing`."""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from src.catalog.schemas import FornecedorParaSKU


class MotivoSemCompra(StrEnum):
    SEM_GIRO = "sem_giro"
    SEM_FORNECEDOR = "sem_fornecedor"
    ACIMA_DO_PONTO_DE_REPOSICAO = "acima_do_ponto_de_reposicao"


class TipoAlerta(StrEnum):
    RUPTURA_ANTES_DA_CHEGADA = "ruptura_antes_da_chegada"


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


class SugestaoPedido(BaseModel):
    """Sugestão de compra de um SKU.

    Sempre existe: quando não há o que comprar, `quantidade` é 0 e `motivo`
    diz por quê. `calculo` fica ausente quando o motivo impede o cálculo
    (sem giro, sem fornecedor).
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
