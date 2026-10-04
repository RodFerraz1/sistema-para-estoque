"""Módulo `reposicao`: o painel do repositor e a detecção de queda de venda.

Queda de venda é conta, sem Jev (ADR-0002). Dia aberto é um dia em que a loja inteira (os
SKUs ativos) vendeu ao menos uma peça: domingos e feriados saem sem calendário. A janela
observada são os últimos `dias_observados_queda` dias abertos antes de hoje, e a venda
diária base é a média dos `DIAS_ABERTOS_DA_BASE` dias abertos anteriores a ela. O SKU tem
queda quando a base chega à `venda_diaria_minima_queda` e a chance de vender no máximo o
que vendeu na janela, numa Poisson de média base vezes os dias da janela, fica abaixo do
`limiar_queda`.

Com estoque disponível, a suspeita é a gôndola e o SKU vai para o painel do repositor. Sem
estoque, o comprador já o vê em ruptura ou entrega atrasada, com o selo "parou de vender".
"""
from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta

from src.catalog.service import Catalog, palavras_da_busca, sku_contem_todas
from src.inventory.service import Inventory
from src.politica_compra.repositorio import PoliticaCompraRepositorio
from src.politica_compra.schemas import ParametrosPolitica
from src.reposicao.schemas import (
    DiaObservado,
    FiltroReposicao,
    ItemQuedaDeVenda,
    PainelDoRepositor,
    QuedaDeVenda,
)
from src.sales.schemas import VendasDoDia
from src.sales.service import Sales

Relogio = Callable[[], datetime]

DIAS_ABERTOS_DA_BASE = 28


def agora_utc() -> datetime:
    return datetime.now(UTC)


def poisson_ate(k: int, media: float) -> float:
    """P(X <= k) numa Poisson de média `media`, somada em log para média alta não zerar."""
    if media <= 0:
        return 1.0
    log_termo = -media
    total = math.exp(log_termo)
    for i in range(1, k + 1):
        log_termo += math.log(media) - math.log(i)
        total += math.exp(log_termo)
    return min(total, 1.0)


def _desde(hoje: date, parametros: ParametrosPolitica) -> datetime:
    """Dias corridos que cobrem, com folga para domingos e feriados, os dias abertos da
    janela e da base."""
    dias = (DIAS_ABERTOS_DA_BASE + parametros.dias_observados_queda) * 3 // 2
    return datetime.combine(hoje - timedelta(days=dias), time(), tzinfo=UTC)


def _dias_abertos(vendas: dict[str, dict[date, int]], hoje: date) -> list[date]:
    """Do mais recente ao mais antigo, antes de hoje."""
    vendeu = {dia for por_dia in vendas.values() for dia, quantidade in por_dia.items() if quantidade > 0}
    return sorted((dia for dia in vendeu if dia < hoje), reverse=True)


def quedas_de_venda(
    vendas_diarias: dict[str, list[VendasDoDia]], hoje: date, parametros: ParametrosPolitica
) -> dict[str, QuedaDeVenda]:
    """Os SKUs com queda de venda. Sem dias abertos que bastem para a janela e para um dia
    de base, nenhum."""
    vendas = {codigo: {v.dia: v.quantidade for v in dias} for codigo, dias in vendas_diarias.items()}
    abertos = _dias_abertos(vendas, hoje)
    n = parametros.dias_observados_queda
    janela = list(reversed(abertos[:n]))
    base = abertos[n : n + DIAS_ABERTOS_DA_BASE]
    if len(janela) < n or not base:
        return {}
    quedas: dict[str, QuedaDeVenda] = {}
    for codigo, por_dia in vendas.items():
        venda_diaria_base = sum(por_dia.get(dia, 0) for dia in base) / len(base)
        if venda_diaria_base < parametros.venda_diaria_minima_queda:
            continue
        ultimos_dias = [DiaObservado(dia=dia, quantidade=por_dia.get(dia, 0)) for dia in janela]
        vendido = sum(d.quantidade for d in ultimos_dias)
        probabilidade = poisson_ate(vendido, venda_diaria_base * n)
        if probabilidade < parametros.limiar_queda:
            quedas[codigo] = QuedaDeVenda(
                sku_code=codigo,
                venda_diaria_base=venda_diaria_base,
                ultimos_dias=ultimos_dias,
                probabilidade=probabilidade,
            )
    return quedas


class Reposicao:
    def __init__(
        self,
        catalog: Catalog,
        inventory: Inventory,
        sales: Sales,
        politicas: PoliticaCompraRepositorio,
        *,
        relogio: Relogio = agora_utc,
    ) -> None:
        self._catalog = catalog
        self._inventory = inventory
        self._sales = sales
        self._politicas = politicas
        self._relogio = relogio

    def quedas_de_venda(self, parametros: ParametrosPolitica) -> dict[str, QuedaDeVenda]:
        """As quedas de venda de todos os SKUs ativos, com ou sem estoque, numa leitura só
        das vendas diárias."""
        hoje = self._relogio().astimezone(UTC).date()
        return quedas_de_venda(self._sales.vendas_diarias_de_todos(_desde(hoje, parametros)), hoje, parametros)

    def painel(self, filtro: FiltroReposicao | None = None) -> PainelDoRepositor:
        """Os SKUs ativos com queda de venda e disponível maior que zero, da maior venda
        perdida para a menor (o código desempata). Um número fixo de leituras."""
        filtro = filtro or FiltroReposicao()
        palavras = palavras_da_busca(filtro.busca or "")
        quedas = self.quedas_de_venda(self._politicas.ativa().parametros)
        estoques = self._inventory.estoques()
        itens = [
            ItemQuedaDeVenda(sku=sku, disponivel=estoque.quantidade_disponivel, queda=queda)
            for sku in self._catalog.listar_skus()
            if (queda := quedas.get(sku.sku_code)) is not None
            and (estoque := estoques.get(sku.sku_code)) is not None
            and estoque.quantidade_disponivel > 0
            and (not palavras or sku_contem_todas(sku, palavras))
            and (not filtro.categoria or sku.categoria == filtro.categoria)
        ]
        itens.sort(key=lambda i: (-i.queda.venda_perdida, i.sku.sku_code))
        return PainelDoRepositor(quedas_de_venda=itens)
