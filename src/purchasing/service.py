"""Módulo `purchasing`: sugere quanto comprar de um SKU e de quem.

Mecanismo fixo, parâmetros da política de compra ativa (ADR-0003). Só lê
dos módulos de domínio; não fala com o `ERPAdapter` diretamente.
"""
from __future__ import annotations

import math
from datetime import datetime

from src.catalog.schemas import FornecedorParaSKU
from src.ficha_sku.service import FichaSKU
from src.inventory.service import Inventory
from src.politica_compra.repositorio import PoliticaCompraRepositorio
from src.politica_compra.schemas import (
    DIAS_POR_MES,
    LeadTimeBase,
    ParametrosPolitica,
    PoliticaCompra,
)
from src.purchasing.schemas import (
    Alerta,
    LeadTimeOrigem,
    MemoriaCalculo,
    MotivoSemCompra,
    SugestaoPedido,
    TipoAlerta,
)
from src.sales.service import Sales


def _lead_time(
    fornecedor: FornecedorParaSKU, base: LeadTimeBase
) -> tuple[int, LeadTimeOrigem]:
    contratado = fornecedor.lead_time_dias_contratado
    observado = fornecedor.lead_time_dias_observado
    if observado is None or base == LeadTimeBase.CONTRATADO:
        return contratado, LeadTimeOrigem.CONTRATADO
    if base == LeadTimeBase.MAIOR and contratado >= observado:
        return contratado, LeadTimeOrigem.CONTRATADO
    return observado, LeadTimeOrigem.OBSERVADO


def _consumo_no_lead_time(giro: float, lead_time_dias: int) -> float:
    return giro * lead_time_dias / DIAS_POR_MES


def _calcular(
    fornecedor: FornecedorParaSKU,
    *,
    giro: float,
    disponivel: int,
    em_transito: int,
    parametros: ParametrosPolitica,
) -> tuple[MemoriaCalculo, int]:
    """Memória de cálculo e quantidade a comprar deste fornecedor."""
    lead_time_dias, lead_time_origem = _lead_time(fornecedor, parametros.lead_time_base)
    posicao = disponivel + em_transito
    estoque_na_chegada = max(0.0, posicao - _consumo_no_lead_time(giro, lead_time_dias))
    piso_reposicao_meses = parametros.piso_reposicao_dias / DIAS_POR_MES

    qtd_necessaria = 0
    if estoque_na_chegada < giro * piso_reposicao_meses:
        alvo = giro * (piso_reposicao_meses + parametros.ciclo_compra_meses)
        # Arredonda antes do ceil pra erro de ponto flutuante não virar uma
        # unidade a mais (200.00000000000003 -> 201).
        qtd_necessaria = math.ceil(round(alvo - estoque_na_chegada, 6))
    quantidade = max(qtd_necessaria, fornecedor.moq_unidades) if qtd_necessaria > 0 else 0

    calculo = MemoriaCalculo(
        giro_mensal=giro,
        disponivel=disponivel,
        em_transito=em_transito,
        posicao=posicao,
        lead_time_dias=lead_time_dias,
        lead_time_origem=lead_time_origem,
        estoque_na_chegada=estoque_na_chegada,
        qtd_necessaria=qtd_necessaria,
        cobertura_na_chegada_meses=(estoque_na_chegada + quantidade) / giro,
    )
    return calculo, quantidade


def _alertas(calculo: MemoriaCalculo) -> list[Alerta]:
    alertas: list[Alerta] = []
    if calculo.posicao < _consumo_no_lead_time(calculo.giro_mensal, calculo.lead_time_dias):
        dias_cobertos = calculo.posicao / calculo.giro_mensal * DIAS_POR_MES
        alertas.append(
            Alerta(
                tipo=TipoAlerta.RUPTURA_ANTES_DA_CHEGADA,
                mensagem=(
                    f"O estoque acaba antes da compra chegar: a posição de "
                    f"{calculo.posicao} unidades cobre cerca de {dias_cobertos:.0f} "
                    f"dias e o lead time é de {calculo.lead_time_dias} dias."
                ),
            )
        )
    return alertas


def _sem_compra(
    sku_code: str,
    politica: PoliticaCompra,
    motivo: MotivoSemCompra,
    calculo: MemoriaCalculo | None = None,
) -> SugestaoPedido:
    return SugestaoPedido(
        sku_code=sku_code,
        quantidade=0,
        motivo=motivo,
        fornecedor=None,
        valor_estimado_centavos=0,
        calculo=calculo,
        alertas=[],
        politica_versao=politica.versao,
    )


class Purchasing:
    def __init__(
        self,
        ficha_sku: FichaSKU,
        inventory: Inventory,
        sales: Sales,
        politicas: PoliticaCompraRepositorio,
        *,
        now: datetime | None = None,
    ) -> None:
        self._ficha_sku = ficha_sku
        self._inventory = inventory
        self._sales = sales
        self._politicas = politicas
        self._now = now

    def sugerir_pedido(self, sku_code: str) -> SugestaoPedido | None:
        """Sugestão calculada na hora com a política ativa.

        `None` para SKU inexistente. Propaga `SKUSemEstoque` do `ficha_sku`.
        """
        ficha = self._ficha_sku.completa(sku_code)
        if ficha is None:
            return None
        politica = self._politicas.ativa()

        giro = ficha.giro.unidades_por_mes
        if giro == 0:
            return _sem_compra(sku_code, politica, MotivoSemCompra.SEM_GIRO)
        if not ficha.fornecedores:
            return _sem_compra(sku_code, politica, MotivoSemCompra.SEM_FORNECEDOR)

        # Por ora sempre o mais barato, a ordem que `fornecedores_de` já devolve.
        fornecedor = ficha.fornecedores[0]
        calculo, quantidade = _calcular(
            fornecedor,
            giro=giro,
            disponivel=ficha.estoque.quantidade_disponivel,
            em_transito=self._inventory.em_transito(sku_code).total_unidades,
            parametros=politica.parametros,
        )
        if quantidade == 0:
            return _sem_compra(
                sku_code, politica, MotivoSemCompra.ACIMA_DO_PONTO_DE_REPOSICAO, calculo
            )
        return SugestaoPedido(
            sku_code=sku_code,
            quantidade=quantidade,
            motivo=None,
            fornecedor=fornecedor,
            # `preco_unitario_reais` já guarda centavos, apesar do nome.
            valor_estimado_centavos=quantidade * fornecedor.preco_unitario_reais,
            calculo=calculo,
            alertas=_alertas(calculo),
            politica_versao=politica.versao,
        )
