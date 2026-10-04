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

A vendedora que vê a gôndola vazia avisa o repositor, com o setor da loja. O aviso de
gôndola vazia entra no topo do painel do repositor e fica aberto até uma verificação do
mesmo SKU registrada depois dele, que notifica a vendedora. O setor do último aviso, ou o
que a verificação corrigiu, é o setor conhecido do SKU.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4

from src.catalog.schemas import SKU
from src.catalog.service import Catalog, SKUInativo, SKUNaoEncontrado, palavras_da_busca, sku_contem_todas
from src.ficha_sku.service import SKUSemEstoque
from src.inventory.schemas import Estoque
from src.inventory.service import Inventory
from src.notificacoes.schemas import Condicao, TipoEpisodio
from src.notificacoes.service import Notificacoes
from src.politica_compra.repositorio import PoliticaCompraRepositorio
from src.politica_compra.schemas import ParametrosPolitica
from src.reposicao.repositorio import AvisosGondolaRepositorio, SetoresRepositorio, VerificacoesRepositorio
from src.reposicao.schemas import (
    AvisoGondola,
    DiaObservado,
    FiltroReposicao,
    ItemAvisoGondola,
    ItemQuedaDeVenda,
    MeuAvisoGondola,
    PainelDoRepositor,
    QuedaDeVenda,
    ResultadoVerificacao,
    Setor,
    SetorDoSku,
    VerificacaoGondola,
)
from src.sales.schemas import VendasDoDia
from src.sales.service import Sales
from src.usuarios.schemas import Usuario

Relogio = Callable[[], datetime]

DIAS_ABERTOS_DA_BASE = 28
PRAZO_DE_MEUS_AVISOS = timedelta(days=30)
TIPOS_DE_EPISODIO: tuple[TipoEpisodio, ...] = ("queda_de_venda",)


class SetorNaoEncontrado(Exception):
    def __init__(self, setor_id: UUID) -> None:
        super().__init__(f"Setor {setor_id} não encontrado.")
        self.setor_id = setor_id


class SetorInativo(Exception):
    def __init__(self, setor: Setor) -> None:
        super().__init__(f"O setor {setor.nome} foi desativado.")
        self.setor = setor


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


def _aberto(aviso: AvisoGondola, ultima_verificacao: VerificacaoGondola | None) -> bool:
    """Nenhuma verificação do SKU registrada depois do aviso."""
    return ultima_verificacao is None or ultima_verificacao.criado_em < aviso.criado_em


class Reposicao:
    def __init__(
        self,
        catalog: Catalog,
        inventory: Inventory,
        sales: Sales,
        politicas: PoliticaCompraRepositorio,
        verificacoes: VerificacoesRepositorio,
        setores: SetoresRepositorio,
        avisos: AvisosGondolaRepositorio,
        notificacoes: Notificacoes,
        *,
        relogio: Relogio = agora_utc,
    ) -> None:
        self._catalog = catalog
        self._inventory = inventory
        self._sales = sales
        self._politicas = politicas
        self._verificacoes = verificacoes
        self._setores = setores
        self._avisos = avisos
        self._notificacoes = notificacoes
        self._relogio = relogio

    def quedas_de_venda(self, parametros: ParametrosPolitica) -> dict[str, QuedaDeVenda]:
        """As quedas de venda de todos os SKUs ativos, com ou sem estoque, numa leitura só
        das vendas diárias."""
        hoje = self._relogio().astimezone(UTC).date()
        return quedas_de_venda(self._sales.vendas_diarias_de_todos(_desde(hoje, parametros)), hoje, parametros)

    def _na_lista(
        self, skus: list[SKU], estoques: dict[str, Estoque], verificacoes: dict[str, VerificacaoGondola]
    ) -> list[ItemQuedaDeVenda]:
        quedas = self.quedas_de_venda(self._politicas.ativa().parametros)
        return [
            ItemQuedaDeVenda(sku=sku, disponivel=estoque.quantidade_disponivel, queda=queda)
            for sku in skus
            if (queda := quedas.get(sku.sku_code)) is not None
            and (estoque := estoques.get(sku.sku_code)) is not None
            and estoque.quantidade_disponivel > 0
            and not _ainda_verificado(queda, verificacoes.get(sku.sku_code))
        ]

    def _avisos_abertos(self, verificacoes: dict[str, VerificacaoGondola]) -> dict[str, list[AvisoGondola]]:
        """Por SKU, do mais antigo para o mais recente."""
        abertos: dict[str, list[AvisoGondola]] = {}
        for aviso in reversed(self._avisos.listar()):
            if _aberto(aviso, verificacoes.get(aviso.sku_code)):
                abertos.setdefault(aviso.sku_code, []).append(aviso)
        return abertos

    def painel(self, filtro: FiltroReposicao | None = None) -> PainelDoRepositor:
        """Primeiro os SKUs ativos com aviso de gôndola vazia aberto, do aviso mais antigo
        para o mais recente. Depois os SKUs ativos com queda de venda e disponível maior que
        zero, menos os verificados sem um dia aberto inteiro depois, da maior venda perdida
        para a menor (o código desempata). Um SKU com aviso e queda fica só no primeiro
        grupo, com a queda. O setor de cada SKU é o conhecido. Um número fixo de leituras."""
        filtro = filtro or FiltroReposicao()
        palavras = palavras_da_busca(filtro.busca or "")
        skus = self._catalog.listar_skus()
        estoques = self._inventory.estoques()
        verificacoes = self._verificacoes.ultimas()
        quedas = {item.sku.sku_code: item for item in self._na_lista(skus, estoques, verificacoes)}
        abertos = self._avisos_abertos(verificacoes)
        setores = {s.id: s for s in self._setores.listar()}
        setor_do_sku = {codigo: setores[s.setor_id] for codigo, s in self._setores.dos_skus().items()}

        def passa(sku: SKU) -> bool:
            setor = setor_do_sku.get(sku.sku_code)
            return (
                (not palavras or sku_contem_todas(sku, palavras))
                and (not filtro.categoria or sku.categoria == filtro.categoria)
                and (not filtro.setor_id or (setor is not None and setor.id == filtro.setor_id))
            )

        avisos = [
            ItemAvisoGondola(
                sku=sku,
                disponivel=estoque.quantidade_disponivel if (estoque := estoques.get(sku.sku_code)) else 0,
                avisos=abertos[sku.sku_code],
                queda=queda.queda if (queda := quedas.get(sku.sku_code)) else None,
                setor=setor_do_sku.get(sku.sku_code),
            )
            for sku in skus
            if sku.sku_code in abertos and passa(sku)
        ]
        avisos.sort(key=lambda i: (i.avisos[0].criado_em, i.sku.sku_code))
        itens = [
            item.model_copy(update={"setor": setor_do_sku.get(codigo)})
            for codigo, item in quedas.items()
            if codigo not in abertos and passa(item.sku)
        ]
        itens.sort(key=lambda i: (-i.queda.venda_perdida, i.sku.sku_code))
        return PainelDoRepositor(avisos_de_gondola=avisos, quedas_de_venda=itens)

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
            for item in self._na_lista(
                self._catalog.listar_skus(), self._inventory.estoques(), self._verificacoes.ultimas()
            )
        ]
        self._notificacoes.varrer(TIPOS_DE_EPISODIO, condicoes)

    def _sku_ativo_com_estoque(self, sku_code: str) -> tuple[SKU, int]:
        sku = self._catalog.carregar_sku(sku_code)
        if sku is None:
            raise SKUNaoEncontrado(sku_code)
        if not sku.ativo:
            raise SKUInativo(sku_code)
        estoque = self._inventory.estoque_atual(sku_code)
        if estoque is None:
            raise SKUSemEstoque(sku_code)
        return sku, estoque.quantidade_disponivel

    def _setor_ativo(self, setor_id: UUID) -> Setor:
        setor = self._setores.carregar(setor_id)
        if setor is None:
            raise SetorNaoEncontrado(setor_id)
        if not setor.ativo:
            raise SetorInativo(setor)
        return setor

    def registrar_verificacao(
        self,
        sku_code: str,
        resultado: ResultadoVerificacao,
        autor: Usuario,
        comentario: str | None = None,
        setor_id: UUID | None = None,
    ) -> VerificacaoGondola:
        """Guarda o disponível do ERP no momento. Com `setor_id`, corrige o setor conhecido
        do SKU. Fecha os avisos de gôndola vazia abertos do SKU e notifica uma vez cada
        vendedora que avisou. Lança `SKUNaoEncontrado`, `SKUInativo`, `SKUSemEstoque`,
        `SetorNaoEncontrado` e `SetorInativo`."""
        sku, disponivel = self._sku_ativo_com_estoque(sku_code)
        setor = self._setor_ativo(setor_id) if setor_id is not None else None
        ultima = self._verificacoes.ultimas().get(sku_code)
        abertos = [a for a in self._avisos.listar(sku_code) if _aberto(a, ultima)]
        agora = self._relogio()
        verificacao = VerificacaoGondola(
            id=uuid4(),
            sku_code=sku_code,
            resultado=resultado,
            comentario=(comentario or "").strip() or None,
            disponivel_no_erp=disponivel,
            verificado_por=autor.nome,
            usuario_id=autor.id,
            criado_em=agora,
        )
        self._verificacoes.gravar(verificacao)
        if setor is not None:
            self._setores.lembrar(SetorDoSku(sku_code=sku_code, setor_id=setor.id, atualizado_em=agora, usuario_id=autor.id))
        for usuario_id in dict.fromkeys(a.usuario_id for a in abertos):
            self._notificacoes.registrar(
                Condicao(
                    tipo="verificacao_sobre_aviso",
                    sku_code=sku_code,
                    papel_destino="vendas",
                    usuario_destino=usuario_id,
                    detalhe={
                        "produto_nome": sku.produto_nome,
                        "cor": sku.cor,
                        "tamanho": sku.tamanho,
                        "resultado": resultado,
                        "comentario": verificacao.comentario,
                        "verificado_por": autor.nome,
                    },
                ),
                agora,
            )
        return verificacao

    def registrar_aviso_gondola(
        self, sku_code: str, setor_id: UUID, autor: Usuario, comentario: str | None = None
    ) -> AvisoGondola:
        """Guarda o disponível do ERP no momento, lembra o setor como o setor conhecido do SKU
        e notifica na hora o papel `reposicao`. Lança `SKUNaoEncontrado`, `SKUInativo`,
        `SKUSemEstoque`, `SetorNaoEncontrado` e `SetorInativo`."""
        sku, disponivel = self._sku_ativo_com_estoque(sku_code)
        setor = self._setor_ativo(setor_id)
        aviso = AvisoGondola(
            id=uuid4(),
            sku_code=sku_code,
            setor_id=setor.id,
            comentario=(comentario or "").strip() or None,
            disponivel_no_erp=disponivel,
            avisado_por=autor.nome,
            usuario_id=autor.id,
            criado_em=self._relogio(),
        )
        self._avisos.gravar(aviso)
        self._setores.lembrar(
            SetorDoSku(sku_code=sku_code, setor_id=setor.id, atualizado_em=aviso.criado_em, usuario_id=autor.id)
        )
        self._notificacoes.registrar(
            Condicao(
                tipo="gondola_vazia",
                sku_code=sku_code,
                papel_destino="reposicao",
                detalhe={
                    "produto_nome": sku.produto_nome,
                    "cor": sku.cor,
                    "tamanho": sku.tamanho,
                    "setor": setor.nome,
                    "avisado_por": autor.nome,
                    "comentario": aviso.comentario,
                    "disponivel_no_erp": disponivel,
                },
            ),
            aviso.criado_em,
        )
        return aviso

    def meus_avisos_de_gondola(self, autor: Usuario) -> list[MeuAvisoGondola]:
        """Os avisos de gôndola vazia do usuário nos últimos `PRAZO_DE_MEUS_AVISOS`, do mais
        recente para o mais antigo, cada um com a verificação que o fechou, se houve."""
        avisos = self._avisos.do_usuario(autor.id, self._relogio() - PRAZO_DE_MEUS_AVISOS)
        if not avisos:
            return []
        codigos = {a.sku_code for a in avisos}
        verificacoes = self._verificacoes.dos_skus(codigos, min(a.criado_em for a in avisos))[::-1]
        skus = {codigo: self._catalog.carregar_sku(codigo) for codigo in codigos}
        setores = {s.id: s for s in self._setores.listar()}
        return [
            MeuAvisoGondola(
                aviso=a,
                sku=sku,
                setor=setores[a.setor_id],
                verificacao=next(
                    (v for v in verificacoes if v.sku_code == a.sku_code and v.criado_em >= a.criado_em), None
                ),
            )
            for a in avisos
            if (sku := skus[a.sku_code]) is not None
        ]

    def setores(self) -> list[Setor]:
        """Todos, ativos ou não, pelo nome."""
        return self._setores.listar()

    def skus_por_setor(self) -> dict[UUID, int]:
        """Quantos SKUs têm cada setor como setor conhecido."""
        contagem: dict[UUID, int] = {}
        for setor_do_sku in self._setores.dos_skus().values():
            contagem[setor_do_sku.setor_id] = contagem.get(setor_do_sku.setor_id, 0) + 1
        return contagem

    def criar_setor(self, nome: str) -> Setor:
        """Lança `SetorJaExiste`."""
        setor = Setor(id=uuid4(), nome=nome.strip(), ativo=True)
        self._setores.gravar(setor)
        return setor

    def mudar_setor(self, setor_id: UUID, nome: str, ativo: bool) -> Setor:
        """Renomeia, desativa ou reativa. Lança `SetorNaoEncontrado` e `SetorJaExiste`."""
        if self._setores.carregar(setor_id) is None:
            raise SetorNaoEncontrado(setor_id)
        setor = Setor(id=setor_id, nome=nome.strip(), ativo=ativo)
        self._setores.gravar(setor)
        return setor

    def setor_do_sku(self, sku_code: str) -> Setor | None:
        """O setor conhecido do SKU, ativo ou não. Lança `SKUNaoEncontrado`."""
        if self._catalog.carregar_sku(sku_code) is None:
            raise SKUNaoEncontrado(sku_code)
        conhecido = self._setores.do_sku(sku_code)
        return None if conhecido is None else self._setores.carregar(conhecido.setor_id)

    def verificacoes(self, sku_code: str) -> list[VerificacaoGondola]:
        """Da mais recente para a mais antiga."""
        return self._verificacoes.listar(sku_code)

    def ultimas_verificacoes(self) -> dict[str, VerificacaoGondola]:
        """A verificação mais recente de cada SKU que tem alguma."""
        return self._verificacoes.ultimas()
