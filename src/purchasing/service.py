"""Módulo `purchasing`: sugere quanto comprar de um SKU e de quem.

Mecanismo fixo, parâmetros da política de compra ativa (ADR-0003). A conta sai do
retrato do `ficha_sku`: o do estoque inteiro no painel, o de um SKU só na tela do SKU,
para os dois caminhos darem a mesma sugestão. Lê dos módulos de domínio; do `ERPAdapter` só lê os pedidos de compra, que não têm
módulo de leitura próprio. O Copilot não escreve no ERP (ADR-0005).
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from src.catalog.schemas import SKU, FornecedorParaSKU
from src.catalog.service import Catalog
from src.erp_adapter.port import ERPAdapter
from src.ficha_sku.schemas import Ficha, Retrato
from src.ficha_sku.service import FichaSKU
from src.inventory.schemas import dias_de_cobertura
from src.politica_compra.repositorio import PoliticaCompraRepositorio
from src.politica_compra.schemas import (
    DIAS_POR_MES,
    CriterioFornecedor,
    LeadTimeBase,
    ParametrosPolitica,
    PoliticaCompra,
    SazonalidadeModo,
)
from src.purchasing.schemas import (
    Alerta,
    LeadTimeOrigem,
    MemoriaCalculo,
    MotivoSemCompra,
    PrecoPago,
    ReferenciasDePreco,
    Substituto,
    SugestaoPedido,
    TipoAlerta,
)


def _lead_time(
    fornecedor: FornecedorParaSKU, base: LeadTimeBase
) -> tuple[int, LeadTimeOrigem]:
    if base == LeadTimeBase.IGNORAR:
        return 0, LeadTimeOrigem.IGNORADO
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
    # O critério de fornecedor ordena pelo prazo do fornecedor mesmo quando o cálculo o
    # ignora: o que ele costuma cumprir, ou o contratado se não houver observado.
    lead_time_para_escolha: int

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
    # Com piso + ciclo no limite do teto (o padrão), arredondar a compra para unidades
    # inteiras passa do teto por menos de uma unidade. Isso não conta como violar o teto.
    teto_unidades = giro * parametros.teto_meses
    base_da_escolha = (
        LeadTimeBase.OBSERVADO if parametros.lead_time_base == LeadTimeBase.IGNORAR else parametros.lead_time_base
    )
    return _Candidato(
        fornecedor=fornecedor,
        calculo=calculo,
        quantidade=quantidade,
        cabe_no_teto=quantidade == 0 or estoque_na_chegada + quantidade < teto_unidades + 1,
        lead_time_para_escolha=_lead_time(fornecedor, base_da_escolha)[0],
    )


_CHAVES_DE_ORDEM: dict[CriterioFornecedor, Callable[[_Candidato], tuple[int, int]]] = {
    CriterioFornecedor.MENOR_PRECO: lambda c: (
        c.fornecedor.preco_unitario_reais,
        c.lead_time_para_escolha,
    ),
    CriterioFornecedor.MENOR_LEAD_TIME: lambda c: (
        c.lead_time_para_escolha,
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
            f"Nenhum fornecedor cabe no teto de {_formatar_meses(teto_meses)} meses "
            f"({dias_de_cobertura(teto_meses):.0f} dias): comprando {escolhido.quantidade} unidades do fornecedor "
            f"{fornecedor.fornecedor_nome} (MOQ {fornecedor.moq_unidades}), "
            f"a cobertura na chegada fica em "
            f"{escolhido.calculo.cobertura_na_chegada_dias:.0f} dias."
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


_NOMES_DOS_MESES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def _meses_do_calendario(inicio: datetime, fim: datetime) -> list[int]:
    """Meses (1-12) tocados de `inicio` a `fim`, inclusive, em ordem e sem repetir."""
    meses: list[int] = []
    ano, mes = inicio.year, inicio.month
    while (ano, mes) <= (fim.year, fim.month) and mes not in meses:
        meses.append(mes)
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    return meses


def _listar_por_extenso(nomes: list[str]) -> str:
    if len(nomes) == 1:
        return nomes[0]
    return ", ".join(nomes[:-1]) + " e " + nomes[-1]


def _alerta_periodo_sazonal(
    escolhido: _Candidato, parametros: ParametrosPolitica, agora: datetime
) -> Alerta | None:
    if parametros.sazonalidade_modo == SazonalidadeModo.IGNORAR:
        return None
    chegada = agora + timedelta(days=escolhido.calculo.lead_time_dias)
    fim_do_ciclo = chegada + timedelta(days=parametros.ciclo_compra_meses * DIAS_POR_MES)
    quentes = [
        m
        for m in _meses_do_calendario(chegada, fim_do_ciclo)
        if m in parametros.meses_quentes
    ]
    if not quentes:
        return None
    meses = _listar_por_extenso([_NOMES_DOS_MESES[m - 1] for m in quentes])
    return Alerta(
        tipo=TipoAlerta.PERIODO_SAZONAL,
        mensagem=(
            f"A compra chega em época forte ({meses}). Pela R2, dá "
            f"pra comprar até {_formatar_meses(parametros.extra_sazonal_meses)} "
            f"meses de estoque a mais, com registro em ata."
        ),
    )


def _alertas(
    escolhido: _Candidato, parametros: ParametrosPolitica, agora: datetime
) -> list[Alerta]:
    alertas = [
        _alerta_ruptura(escolhido),
        _alerta_viola_teto(escolhido, parametros.teto_meses),
        _alerta_abaixo_pedido_minimo(escolhido),
        _alerta_lead_time_observado(escolhido),
        _alerta_periodo_sazonal(escolhido, parametros, agora),
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


MAX_SUBSTITUTOS = 10


def _sku_novo(ficha: Ficha, parametros: ParametrosPolitica, agora: datetime) -> bool:
    if ficha.primeira_venda is None:
        return False
    return agora - ficha.primeira_venda < timedelta(days=parametros.dias_historico_minimo)


def _sugestao(ficha: Ficha, politica: PoliticaCompra, agora: datetime) -> SugestaoPedido:
    sku_code = ficha.sku.sku_code
    if _sku_novo(ficha, politica.parametros, agora):
        return _sem_compra(sku_code, politica, MotivoSemCompra.SKU_NOVO)
    giro = ficha.giro.unidades_por_mes
    if giro == 0:
        return _sem_compra(sku_code, politica, MotivoSemCompra.SEM_GIRO)
    if not ficha.fornecedores:
        return _sem_compra(sku_code, politica, MotivoSemCompra.SEM_FORNECEDOR)

    candidatos = [
        _calcular(
            fornecedor,
            giro=giro,
            disponivel=ficha.estoque.quantidade_disponivel,
            em_transito=ficha.em_transito,
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
        alertas=_alertas(escolhido, politica.parametros, agora),
        politica_versao=politica.versao,
    )


class Purchasing:
    def __init__(
        self,
        catalog: Catalog,
        ficha_sku: FichaSKU,
        politicas: PoliticaCompraRepositorio,
        erp: ERPAdapter,
        *,
        now: datetime | None = None,
    ) -> None:
        self._catalog = catalog
        self._ficha_sku = ficha_sku
        self._politicas = politicas
        self._erp = erp
        self._now = now

    def _agora(self) -> datetime:
        return self._now or datetime.now(UTC)

    def sugerir_pedido(self, sku_code: str) -> SugestaoPedido | None:
        """Sugestão calculada na hora com a política ativa, pela mesma conta de
        `sugerir_pedidos` sobre o retrato deste SKU.

        `None` para SKU inexistente. Propaga `SKUSemEstoque` do `ficha_sku`.
        """
        retrato = self._ficha_sku.retrato_de(sku_code)
        if retrato is None:
            return None
        return self.sugerir_pedidos(retrato)[sku_code]

    def sugerir_pedidos(self, retrato: Retrato) -> dict[str, SugestaoPedido]:
        """Sugestão de cada SKU com ficha no retrato, por `sku_code`, com a política ativa."""
        politica = self._politicas.ativa()
        agora = self._agora()
        return {codigo: _sugestao(ficha, politica, agora) for codigo, ficha in retrato.fichas.items()}

    def referencias_de_preco(self, sku_code: str) -> ReferenciasDePreco | None:
        """Histórico de preço pago, preço atual por fornecedor e substitutos do SKU.
        `None` para SKU inexistente."""
        sku = self._catalog.carregar_sku(sku_code)
        if sku is None:
            return None
        historico = [
            PrecoPago(
                data=item.criado_em,
                fornecedor_nome=item.fornecedor_nome,
                preco_unitario_centavos=item.preco_unitario_centavos,
                quantidade=item.quantidade,
                status=item.status,
            )
            for item in self._erp.itens_de_pedido_de(sku_code)
            if item.status != "cancelado"
        ]
        return ReferenciasDePreco(
            historico=historico,
            precos_atuais=self._catalog.fornecedores_de(sku_code),
            substitutos=self._substitutos(sku),
        )

    def _substitutos(self, sku: SKU) -> list[Substituto]:
        substitutos: list[Substituto] = []
        for outro in self._catalog.listar_skus():
            if outro.produto_id == sku.produto_id or (outro.categoria, outro.tamanho) != (sku.categoria, sku.tamanho):
                continue
            # `fornecedores_de` vem do mais barato ao mais caro.
            mais_barato = next(iter(self._catalog.fornecedores_de(outro.sku_code)), None)
            if mais_barato is not None:
                substitutos.append(
                    Substituto(
                        sku=outro,
                        # `preco_unitario_reais` já guarda centavos, apesar do nome.
                        preco_unitario_centavos=mais_barato.preco_unitario_reais,
                        fornecedor_nome=mais_barato.fornecedor_nome,
                    )
                )
        substitutos.sort(key=lambda s: (s.preco_unitario_centavos, s.sku.sku_code))
        return substitutos[:MAX_SUBSTITUTOS]
