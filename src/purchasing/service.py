"""Módulo `purchasing`: sugere quanto comprar de um SKU e de quem.

Mecanismo fixo, parâmetros da política de compra ativa (ADR-0003). Só lê
dos módulos de domínio; não fala com o `ERPAdapter` diretamente.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from src.catalog.schemas import FornecedorParaSKU
from src.ficha_sku.service import FichaSKU
from src.inventory.service import Inventory
from src.politica_compra.repositorio import PoliticaCompraRepositorio
from src.politica_compra.schemas import (
    DIAS_POR_MES,
    CriterioFornecedor,
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


@dataclass(frozen=True)
class _Candidato:
    fornecedor: FornecedorParaSKU
    calculo: MemoriaCalculo
    quantidade: int
    cabe_no_teto: bool

    @property
    def valor_centavos(self) -> int:
        # `preco_unitario_reais` já guarda centavos, apesar do nome.
        return self.quantidade * self.fornecedor.preco_unitario_reais


def _calcular(
    fornecedor: FornecedorParaSKU,
    *,
    giro: float,
    disponivel: int,
    em_transito: int,
    parametros: ParametrosPolitica,
) -> _Candidato:
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
    cobertura_na_chegada_meses = (estoque_na_chegada + quantidade) / giro

    calculo = MemoriaCalculo(
        giro_mensal=giro,
        disponivel=disponivel,
        em_transito=em_transito,
        posicao=posicao,
        lead_time_dias=lead_time_dias,
        lead_time_origem=lead_time_origem,
        estoque_na_chegada=estoque_na_chegada,
        qtd_necessaria=qtd_necessaria,
        cobertura_na_chegada_meses=cobertura_na_chegada_meses,
    )
    return _Candidato(
        fornecedor=fornecedor,
        calculo=calculo,
        quantidade=quantidade,
        cabe_no_teto=quantidade == 0 or cobertura_na_chegada_meses <= parametros.teto_meses,
    )


_CHAVES_DE_ORDEM: dict[CriterioFornecedor, Callable[[_Candidato], tuple[int, int]]] = {
    CriterioFornecedor.MENOR_PRECO: lambda c: (
        c.fornecedor.preco_unitario_reais,
        c.calculo.lead_time_dias,
    ),
    CriterioFornecedor.MENOR_LEAD_TIME: lambda c: (
        c.calculo.lead_time_dias,
        c.fornecedor.preco_unitario_reais,
    ),
}


def _escolher(candidatos: list[_Candidato], criterio: CriterioFornecedor) -> _Candidato:
    """Primeiro pelo critério que cabe no teto; se nenhum cabe, o primeiro."""
    ordenados = sorted(candidatos, key=_CHAVES_DE_ORDEM[criterio])
    return next((c for c in ordenados if c.cabe_no_teto), ordenados[0])


def _formatar_reais(centavos: int) -> str:
    return "R$ " + f"{centavos / 100:,.2f}".translate(str.maketrans(",.", ".,"))


def _formatar_meses(meses: float) -> str:
    return f"{meses:.1f}".replace(".", ",")


def _alerta_ruptura(escolhido: _Candidato) -> Alerta | None:
    calculo = escolhido.calculo
    if calculo.posicao >= _consumo_no_lead_time(calculo.giro_mensal, calculo.lead_time_dias):
        return None
    dias_cobertos = calculo.posicao / calculo.giro_mensal * DIAS_POR_MES
    return Alerta(
        tipo=TipoAlerta.RUPTURA_ANTES_DA_CHEGADA,
        mensagem=(
            f"O estoque acaba antes da compra chegar: a posição de "
            f"{calculo.posicao} unidades cobre cerca de {dias_cobertos:.0f} "
            f"dias e o lead time é de {calculo.lead_time_dias} dias."
        ),
    )


def _alerta_viola_teto(escolhido: _Candidato, teto_meses: float) -> Alerta | None:
    if escolhido.cabe_no_teto:
        return None
    fornecedor = escolhido.fornecedor
    return Alerta(
        tipo=TipoAlerta.VIOLA_TETO,
        mensagem=(
            f"Nenhum fornecedor cabe no teto de {_formatar_meses(teto_meses)} "
            f"meses: comprando {escolhido.quantidade} unidades do fornecedor "
            f"{fornecedor.fornecedor_nome} (MOQ {fornecedor.moq_unidades}), "
            f"a cobertura na chegada fica em "
            f"{_formatar_meses(escolhido.calculo.cobertura_na_chegada_meses)} meses."
        ),
    )


def _alerta_abaixo_pedido_minimo(escolhido: _Candidato) -> Alerta | None:
    fornecedor = escolhido.fornecedor
    pedido_minimo_centavos = fornecedor.pedido_minimo_reais * 100
    if escolhido.valor_centavos >= pedido_minimo_centavos:
        return None
    return Alerta(
        tipo=TipoAlerta.ABAIXO_PEDIDO_MINIMO,
        mensagem=(
            f"O pedido de {_formatar_reais(escolhido.valor_centavos)} fica abaixo do "
            f"pedido mínimo de {_formatar_reais(pedido_minimo_centavos)} do fornecedor "
            f"{fornecedor.fornecedor_nome}. Junte com outros SKUs dele."
        ),
    )


def _alerta_lead_time_observado(escolhido: _Candidato) -> Alerta | None:
    fornecedor = escolhido.fornecedor
    observado = fornecedor.lead_time_dias_observado
    contratado = fornecedor.lead_time_dias_contratado
    if observado is None or observado <= contratado:
        return None
    return Alerta(
        tipo=TipoAlerta.LEAD_TIME_OBSERVADO_ACIMA_DO_CONTRATADO,
        mensagem=(
            f"O fornecedor {fornecedor.fornecedor_nome} tem entregado em "
            f"{observado} dias, acima dos {contratado} contratados."
        ),
    )


def _alertas(escolhido: _Candidato, parametros: ParametrosPolitica) -> list[Alerta]:
    alertas = [
        _alerta_ruptura(escolhido),
        _alerta_viola_teto(escolhido, parametros.teto_meses),
        _alerta_abaixo_pedido_minimo(escolhido),
        _alerta_lead_time_observado(escolhido),
    ]
    return [a for a in alertas if a is not None]


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

        em_transito = self._inventory.em_transito(sku_code).total_unidades
        candidatos = [
            _calcular(
                fornecedor,
                giro=giro,
                disponivel=ficha.estoque.quantidade_disponivel,
                em_transito=em_transito,
                parametros=politica.parametros,
            )
            for fornecedor in ficha.fornecedores
        ]
        escolhido = _escolher(candidatos, politica.parametros.criterio_fornecedor)
        if escolhido.quantidade == 0:
            return _sem_compra(
                sku_code,
                politica,
                MotivoSemCompra.ACIMA_DO_PONTO_DE_REPOSICAO,
                escolhido.calculo,
            )
        return SugestaoPedido(
            sku_code=sku_code,
            quantidade=escolhido.quantidade,
            motivo=None,
            fornecedor=escolhido.fornecedor,
            valor_estimado_centavos=escolhido.valor_centavos,
            calculo=escolhido.calculo,
            alertas=_alertas(escolhido, politica.parametros),
            politica_versao=politica.versao,
        )
