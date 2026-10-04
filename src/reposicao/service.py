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

O repositor registra a verificação de gôndola do que achou. O SKU verificado sai do painel
dele e só volta quando um dia aberto inteiro depois da verificação fecha e a janela
observada continua com queda: o último dia da janela passa a ser depois do dia da
verificação. O mesmo vale para o episódio `queda_de_venda`, que notifica o repositor do SKU
novo na lista.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4

from src.catalog.service import Catalog, SKUInativo, SKUNaoEncontrado, palavras_da_busca, sku_contem_todas
from src.ficha_sku.service import SKUSemEstoque
from src.inventory.service import Inventory
from src.notificacoes.schemas import Condicao, TipoEpisodio
from src.notificacoes.service import Notificacoes
from src.politica_compra.repositorio import PoliticaCompraRepositorio
from src.politica_compra.schemas import ParametrosPolitica
from src.reposicao.repositorio import VerificacoesRepositorio
from src.reposicao.schemas import (
    DiaObservado,
    FiltroReposicao,
    ItemQuedaDeVenda,
    PainelDoRepositor,
    QuedaDeVenda,
    ResultadoVerificacao,
    VerificacaoGondola,
)
from src.sales.schemas import VendasDoDia
from src.sales.service import Sales
from src.usuarios.schemas import Usuario

Relogio = Callable[[], datetime]

DIAS_ABERTOS_DA_BASE = 28
TIPOS_DE_EPISODIO: tuple[TipoEpisodio, ...] = ("queda_de_venda",)


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


def _ainda_verificado(queda: QuedaDeVenda, verificacao: VerificacaoGondola | None) -> bool:
    """Nenhum dia aberto inteiro fechou depois da verificação."""
    return verificacao is not None and verificacao.criado_em.astimezone(UTC).date() >= queda.ultimos_dias[-1].dia


class Reposicao:
    def __init__(
        self,
        catalog: Catalog,
        inventory: Inventory,
        sales: Sales,
        politicas: PoliticaCompraRepositorio,
        verificacoes: VerificacoesRepositorio,
        notificacoes: Notificacoes,
        *,
        relogio: Relogio = agora_utc,
    ) -> None:
        self._catalog = catalog
        self._inventory = inventory
        self._sales = sales
        self._politicas = politicas
        self._verificacoes = verificacoes
        self._notificacoes = notificacoes
        self._relogio = relogio

    def quedas_de_venda(self, parametros: ParametrosPolitica) -> dict[str, QuedaDeVenda]:
        """As quedas de venda de todos os SKUs ativos, com ou sem estoque, numa leitura só
        das vendas diárias."""
        hoje = self._relogio().astimezone(UTC).date()
        return quedas_de_venda(self._sales.vendas_diarias_de_todos(_desde(hoje, parametros)), hoje, parametros)

    def _na_lista(self) -> list[ItemQuedaDeVenda]:
        quedas = self.quedas_de_venda(self._politicas.ativa().parametros)
        estoques = self._inventory.estoques()
        verificacoes = self._verificacoes.ultimas()
        return [
            ItemQuedaDeVenda(sku=sku, disponivel=estoque.quantidade_disponivel, queda=queda)
            for sku in self._catalog.listar_skus()
            if (queda := quedas.get(sku.sku_code)) is not None
            and (estoque := estoques.get(sku.sku_code)) is not None
            and estoque.quantidade_disponivel > 0
            and not _ainda_verificado(queda, verificacoes.get(sku.sku_code))
        ]

    def painel(self, filtro: FiltroReposicao | None = None) -> PainelDoRepositor:
        """Os SKUs ativos com queda de venda e disponível maior que zero, menos os verificados
        sem um dia aberto inteiro depois, da maior venda perdida para a menor (o código
        desempata). Um número fixo de leituras."""
        filtro = filtro or FiltroReposicao()
        palavras = palavras_da_busca(filtro.busca or "")
        itens = [
            item
            for item in self._na_lista()
            if (not palavras or sku_contem_todas(item.sku, palavras))
            and (not filtro.categoria or item.sku.categoria == filtro.categoria)
        ]
        itens.sort(key=lambda i: (-i.queda.venda_perdida, i.sku.sku_code))
        return PainelDoRepositor(quedas_de_venda=itens)

    def varrer_episodios(self) -> None:
        """Abre e fecha os episódios de queda de venda pelos SKUs do painel do repositor de
        agora."""
        condicoes = [
            Condicao(
                tipo="queda_de_venda",
                sku_code=item.sku.sku_code,
                papel_destino="reposicao",
                detalhe={
                    "produto_nome": item.sku.produto_nome,
                    "cor": item.sku.cor,
                    "tamanho": item.sku.tamanho,
                    "disponivel": item.disponivel,
                    "venda_diaria_base": item.queda.venda_diaria_base,
                    "vendido_na_janela": item.queda.vendido_na_janela,
                    "dias_observados": len(item.queda.ultimos_dias),
                },
            )
            for item in self._na_lista()
        ]
        self._notificacoes.varrer(TIPOS_DE_EPISODIO, condicoes)

    def registrar_verificacao(
        self, sku_code: str, resultado: ResultadoVerificacao, autor: Usuario, comentario: str | None = None
    ) -> VerificacaoGondola:
        """Guarda o disponível do ERP no momento. Lança `SKUNaoEncontrado`, `SKUInativo` e
        `SKUSemEstoque`."""
        sku = self._catalog.carregar_sku(sku_code)
        if sku is None:
            raise SKUNaoEncontrado(sku_code)
        if not sku.ativo:
            raise SKUInativo(sku_code)
        estoque = self._inventory.estoque_atual(sku_code)
        if estoque is None:
            raise SKUSemEstoque(sku_code)
        verificacao = VerificacaoGondola(
            id=uuid4(),
            sku_code=sku_code,
            resultado=resultado,
            comentario=(comentario or "").strip() or None,
            disponivel_no_erp=estoque.quantidade_disponivel,
            verificado_por=autor.nome,
            usuario_id=autor.id,
            criado_em=self._relogio(),
        )
        self._verificacoes.gravar(verificacao)
        return verificacao

    def verificacoes(self, sku_code: str) -> list[VerificacaoGondola]:
        """Da mais recente para a mais antiga."""
        return self._verificacoes.listar(sku_code)

    def ultimas_verificacoes(self) -> dict[str, VerificacaoGondola]:
        """A verificação mais recente de cada SKU que tem alguma."""
        return self._verificacoes.ultimas()
