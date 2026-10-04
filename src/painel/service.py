"""Módulo `painel`: o painel de alertas do comprador chefe, os avisos da equipe de
vendas e as decisões de compra (ADR-0005).

O painel é calculado na hora, sem estado próprio, a partir do retrato do estoque inteiro
(as fichas de todos os SKUs ativos, lidas em lote), da sugestão de pedido de cada um com a
política ativa, dos avisos abertos e da decisão vigente. Não chama o Jev: os sinais do
corpus ficam na tela do SKU.

Aviso aberto é o que não tem decisão de compra do mesmo SKU registrada depois dele.
Decisão vigente é a mais recente do SKU, com menos de `PRAZO_DA_DECISAO` e sem aviso
posterior. Cobrança vigente é a mais recente do pedido, até a nova previsão (inclusive) ou,
sem ela, por `PRAZO_DA_COBRANCA`. Nada é atualizado: tudo sai das datas.

O painel também sabe as condições que notificam o comprador: SKU em ruptura sem decisão
vigente e pedido com entrega atrasada sem cobrança vigente, cada uma só com o motivo
ligado na política. `varrer_episodios` as entrega ao módulo `notificacoes`. O aviso da
equipe de vendas notifica na hora em que é registrado.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from src.catalog.schemas import SKU
from src.catalog.service import Catalog, ordem_por_nome, palavras_da_busca, sku_contem_todas
from src.ficha_sku.schemas import Ficha
from src.ficha_sku.service import FichaSKU
from src.inventory.schemas import Cobertura, EntregaAtrasada, dias_de_atraso, dias_de_cobertura
from src.inventory.service import Inventory
from src.notificacoes.schemas import Condicao, TipoEpisodio
from src.notificacoes.service import Notificacoes
from src.painel.repositorio import AvisosRepositorio, CobrancasRepositorio, DecisoesRepositorio
from src.painel.schemas import (
    GRUPOS,
    Aviso,
    CobrancaEntrega,
    DecisaoCompra,
    EntregaPendente,
    FiltroEstoque,
    FiltroPainel,
    FornecedorComAtraso,
    ItemAlerta,
    ItemDecidido,
    ItemEstoque,
    OrdemEstoque,
    PaginaDeEstoque,
    PainelDeAlertas,
    PedidoAtrasado,
    SKUComEntregaAtrasada,
    TipoAviso,
    TipoDecisao,
)
from src.politica_compra.repositorio import PoliticaCompraRepositorio
from src.politica_compra.schemas import DIAS_POR_MES, MotivoAlerta, ParametrosPolitica
from src.purchasing.schemas import SugestaoPedido
from src.purchasing.service import Purchasing
from src.usuarios.schemas import Usuario

Relogio = Callable[[], datetime]

PRAZO_DA_DECISAO = timedelta(days=7)
PRAZO_DA_COBRANCA = timedelta(days=7)
TIPOS_DE_EPISODIO: tuple[TipoEpisodio, ...] = ("ruptura", "entrega_atrasada")


def agora_utc() -> datetime:
    return datetime.now(UTC)


class SKUNaoEncontrado(LookupError):
    def __init__(self, sku_code: str) -> None:
        super().__init__(f"SKU '{sku_code}' não encontrado")
        self.sku_code = sku_code


class SKUInativo(ValueError):
    def __init__(self, sku_code: str) -> None:
        super().__init__(f"O SKU '{sku_code}' está inativo: o atacadista não compra mais.")
        self.sku_code = sku_code


class QuantidadeObrigatoria(ValueError):
    def __init__(self) -> None:
        super().__init__("vou_comprar exige a quantidade, maior que zero.")


class QuantidadeSoParaComprar(ValueError):
    def __init__(self) -> None:
        super().__init__("A quantidade só vale para vou_comprar.")


class MotivoObrigatorio(ValueError):
    def __init__(self) -> None:
        super().__init__("nao_comprar_agora exige o motivo.")


class PedidoSemEntregaAtrasada(LookupError):
    def __init__(self, pedido_id: UUID) -> None:
        super().__init__(f"O pedido '{pedido_id}' não tem entrega atrasada.")
        self.pedido_id = pedido_id


class NovaPrevisaoNoPassado(ValueError):
    def __init__(self) -> None:
        super().__init__("A nova previsão não pode ser antes de hoje.")


def _opcional(valor: str | None) -> str | None:
    return (valor or "").strip() or None


def _em_ruptura(cobertura: Cobertura, parametros: ParametrosPolitica) -> bool:
    return cobertura.meses is not None and cobertura.meses < parametros.piso_alerta_dias / DIAS_POR_MES


def _motivos(
    sugestao: SugestaoPedido, cobertura: Cobertura, parametros: ParametrosPolitica, com_entrega_atrasada: bool
) -> list[MotivoAlerta]:
    """Os alertas da sugestão, o piso de alerta e a entrega atrasada, filtrados pelos motivos
    de alerta da política."""
    ocorridos = [MotivoAlerta(a.tipo.value) for a in sugestao.alertas]
    if _em_ruptura(cobertura, parametros):
        ocorridos.append(MotivoAlerta.ABAIXO_DO_PISO_ALERTA)
    if com_entrega_atrasada:
        ocorridos.append(MotivoAlerta.ENTREGA_ATRASADA)
    return [m for m in ocorridos if m in parametros.motivos_de_alerta]


def _nome_do_sku(sku: SKU) -> dict[str, str]:
    return {"produto_nome": sku.produto_nome, "cor": sku.cor, "tamanho": sku.tamanho}


def _cobranca_vigente(cobranca: CobrancaEntrega | None, agora: datetime) -> bool:
    if cobranca is None:
        return False
    if cobranca.nova_previsao is not None:
        return agora.date() <= cobranca.nova_previsao
    return agora - cobranca.criado_em < PRAZO_DA_COBRANCA


def _abertos(avisos: list[Aviso], ultima: DecisaoCompra | None) -> list[Aviso]:
    return [a for a in avisos if ultima is None or a.criado_em > ultima.criado_em]


def _vigente(ultima: DecisaoCompra | None, abertos: list[Aviso], agora: datetime) -> DecisaoCompra | None:
    if ultima is None or abertos or agora - ultima.criado_em >= PRAZO_DA_DECISAO:
        return None
    return ultima


def _ordem(item: ItemAlerta) -> tuple[int, bool, bool, float, str]:
    """Pelo grupo; em cada grupo, disponível zero no topo, depois a menor cobertura atual,
    os sem giro no fim e o código para desempatar."""
    cobertura = item.cobertura_atual_meses
    return (GRUPOS.index(item.grupo), item.disponivel > 0, cobertura is None, cobertura or 0.0, item.sku.sku_code)


def _passa_no_sku(filtro: FiltroPainel, palavras: list[str], sku: SKU, ficha: Ficha | None) -> bool:
    if palavras and not sku_contem_todas(sku, palavras):
        return False
    if filtro.categoria and sku.categoria != filtro.categoria:
        return False
    if filtro.fornecedor_id is not None:
        return ficha is not None and any(f.fornecedor_id == filtro.fornecedor_id for f in ficha.fornecedores)
    return True


def _tem_o_motivo(filtro: FiltroPainel, item: ItemAlerta) -> bool:
    if filtro.motivo is None:
        return True
    if filtro.motivo == "aviso":
        return bool(item.avisos_abertos)
    return filtro.motivo in item.motivos


def _passa_no_estoque(filtro: FiltroEstoque, palavras: list[str], ficha: Ficha, parametros: ParametrosPolitica) -> bool:
    if palavras and not sku_contem_todas(ficha.sku, palavras):
        return False
    if filtro.categoria and ficha.sku.categoria != filtro.categoria:
        return False
    if filtro.situacao == "em_ruptura":
        return _em_ruptura(ficha.cobertura, parametros)
    if filtro.situacao == "sem_venda":
        return ficha.cobertura.sem_giro
    if filtro.situacao == "com_transito":
        return ficha.em_transito > 0
    return True


ORDENS_DO_ESTOQUE: dict[OrdemEstoque, Callable[[Ficha], tuple]] = {
    "cobertura": lambda f: (f.cobertura.meses is None, f.cobertura.meses or 0.0, f.sku.sku_code),
    "venda_diaria": lambda f: (-f.giro.unidades_por_mes, f.sku.sku_code),
    "nome": lambda f: (*ordem_por_nome(f.sku), f.sku.sku_code),
}


def _item_de_estoque(ficha: Ficha, parametros: ParametrosPolitica) -> ItemEstoque:
    return ItemEstoque(
        sku=ficha.sku,
        disponivel=ficha.estoque.quantidade_disponivel,
        em_transito=ficha.em_transito,
        venda_media_diaria=ficha.giro.unidades_por_mes / DIAS_POR_MES,
        cobertura_meses=ficha.cobertura.meses,
        em_ruptura=_em_ruptura(ficha.cobertura, parametros),
    )


def _item(
    ficha: Ficha,
    sugestao: SugestaoPedido,
    parametros: ParametrosPolitica,
    avisos: list[Aviso],
    com_entrega_atrasada: bool,
) -> ItemAlerta:
    fornecedor = sugestao.fornecedor if sugestao.quantidade > 0 else None
    return ItemAlerta(
        sku=ficha.sku,
        disponivel=ficha.estoque.quantidade_disponivel,
        cobertura_atual_meses=ficha.cobertura.meses,
        cobertura_na_chegada_sem_compra_meses=(
            sugestao.calculo.cobertura_na_chegada_sem_compra_meses if sugestao.calculo else None
        ),
        motivos=_motivos(sugestao, ficha.cobertura, parametros, com_entrega_atrasada),
        quantidade_sugerida=sugestao.quantidade if fornecedor else None,
        fornecedor_sugerido=fornecedor.fornecedor_nome if fornecedor else None,
        avisos_abertos=avisos,
    )


def _sku_com_entrega(
    entrega: EntregaAtrasada, ficha: Ficha, parametros: ParametrosPolitica
) -> SKUComEntregaAtrasada:
    return SKUComEntregaAtrasada(
        sku=ficha.sku,
        quantidade_pendente=entrega.quantidade_pendente,
        disponivel=ficha.estoque.quantidade_disponivel,
        cobertura_meses=ficha.cobertura.meses,
        em_ruptura=_em_ruptura(ficha.cobertura, parametros),
    )


def _por_fornecedor(
    entregas: list[EntregaAtrasada],
    fichas: dict[str, Ficha],
    parametros: ParametrosPolitica,
    cobrancas: dict[UUID, CobrancaEntrega],
) -> list[FornecedorComAtraso]:
    """Primeiro os fornecedores com algum SKU em ruptura, depois o maior atraso. Os pedidos,
    do maior atraso para o menor; os SKUs de cada pedido, os em ruptura primeiro."""
    por_pedido: dict[UUID, list[EntregaAtrasada]] = {}
    for entrega in entregas:
        por_pedido.setdefault(entrega.pedido_id, []).append(entrega)
    por_fornecedor: dict[UUID, list[PedidoAtrasado]] = {}
    nomes: dict[UUID, str] = {}
    for pedido_id, do_pedido in por_pedido.items():
        primeira = do_pedido[0]
        skus = [_sku_com_entrega(e, fichas[e.sku_code], parametros) for e in do_pedido]
        skus.sort(key=lambda s: (not s.em_ruptura, s.cobertura_meses is None, s.cobertura_meses or 0.0, s.sku.sku_code))
        nomes[primeira.fornecedor_id] = primeira.fornecedor_nome
        por_fornecedor.setdefault(primeira.fornecedor_id, []).append(
            PedidoAtrasado(
                pedido_id=pedido_id,
                status=primeira.status,
                data_prevista_entrega=primeira.data_prevista_entrega,
                dias_de_atraso=primeira.dias_de_atraso,
                skus=skus,
                ultima_cobranca=cobrancas.get(pedido_id),
            )
        )
    fornecedores = [
        FornecedorComAtraso(
            fornecedor_id=fornecedor_id,
            fornecedor_nome=nomes[fornecedor_id],
            pedidos=sorted(pedidos, key=lambda p: (-p.dias_de_atraso, str(p.pedido_id))),
        )
        for fornecedor_id, pedidos in por_fornecedor.items()
    ]
    return sorted(fornecedores, key=lambda f: (not f.tem_sku_em_ruptura, -f.maior_atraso_dias, f.fornecedor_nome))


class Painel:
    def __init__(
        self,
        catalog: Catalog,
        ficha_sku: FichaSKU,
        inventory: Inventory,
        purchasing: Purchasing,
        politicas: PoliticaCompraRepositorio,
        avisos: AvisosRepositorio,
        decisoes: DecisoesRepositorio,
        cobrancas: CobrancasRepositorio,
        notificacoes: Notificacoes,
        *,
        relogio: Relogio = agora_utc,
    ) -> None:
        self._catalog = catalog
        self._ficha_sku = ficha_sku
        self._inventory = inventory
        self._purchasing = purchasing
        self._politicas = politicas
        self._avisos = avisos
        self._decisoes = decisoes
        self._cobrancas = cobrancas
        self._notificacoes = notificacoes
        self._relogio = relogio

    def _sku(self, sku_code: str) -> SKU:
        sku = self._catalog.carregar_sku(sku_code)
        if sku is None:
            raise SKUNaoEncontrado(sku_code)
        return sku

    def registrar_aviso(self, sku_code: str, tipo: TipoAviso, autor: Usuario, comentario: str | None = None) -> Aviso:
        """Notifica o comprador na hora. Lança `SKUNaoEncontrado` e `SKUInativo`."""
        sku = self._sku(sku_code)
        if not sku.ativo:
            raise SKUInativo(sku_code)
        aviso = Aviso(
            id=uuid4(),
            sku_code=sku_code,
            tipo=tipo,
            comentario=_opcional(comentario),
            avisado_por=autor.nome,
            usuario_id=autor.id,
            criado_em=self._relogio(),
        )
        self._avisos.gravar(aviso)
        self._notificacoes.registrar(
            Condicao(
                tipo="aviso",
                sku_code=sku_code,
                papel_destino="comprador",
                detalhe={
                    **_nome_do_sku(sku),
                    "tipo": tipo,
                    "avisado_por": aviso.avisado_por,
                    "comentario": aviso.comentario,
                },
            ),
            aviso.criado_em,
        )
        return aviso

    def registrar_decisao(
        self,
        sku_code: str,
        tipo: TipoDecisao,
        autor: Usuario,
        quantidade: int | None = None,
        motivo: str | None = None,
        comentario: str | None = None,
    ) -> DecisaoCompra:
        """Guarda a sugestão de pedido do momento (quantidade e versão da política). Fecha
        os avisos abertos do SKU e o tira do painel por `PRAZO_DA_DECISAO`. Não cria pedido
        de compra. Lança `SKUNaoEncontrado`, `QuantidadeObrigatoria`,
        `QuantidadeSoParaComprar` e `MotivoObrigatorio`. Propaga `SKUSemEstoque`."""
        motivo = _opcional(motivo)
        if tipo == "vou_comprar" and (quantidade is None or quantidade <= 0):
            raise QuantidadeObrigatoria()
        if tipo != "vou_comprar" and quantidade is not None:
            raise QuantidadeSoParaComprar()
        if tipo == "nao_comprar_agora" and motivo is None:
            raise MotivoObrigatorio()
        self._sku(sku_code)
        sugestao = self._purchasing.sugerir_pedido(sku_code)
        if sugestao is None:
            raise SKUNaoEncontrado(sku_code)
        decisao = DecisaoCompra(
            id=uuid4(),
            sku_code=sku_code,
            tipo=tipo,
            quantidade=quantidade,
            motivo=motivo,
            comentario=_opcional(comentario),
            decidido_por=autor.nome,
            usuario_id=autor.id,
            quantidade_sugerida=sugestao.quantidade,
            politica_versao=sugestao.politica_versao,
            criado_em=self._relogio(),
        )
        self._decisoes.gravar(decisao)
        return decisao

    def registrar_cobranca(
        self, pedido_id: UUID, autor: Usuario, nova_previsao: date | None = None, comentario: str | None = None
    ) -> CobrancaEntrega:
        """Vale para o pedido inteiro e o tira do painel até a nova previsão ou, sem ela, por
        `PRAZO_DA_COBRANCA`. Não muda o ERP. Lança `PedidoSemEntregaAtrasada` e
        `NovaPrevisaoNoPassado`."""
        agora = self._relogio()
        if nova_previsao is not None and nova_previsao < agora.date():
            raise NovaPrevisaoNoPassado()
        entrega = next((e for e in self._inventory.entregas_atrasadas(agora) if e.pedido_id == pedido_id), None)
        if entrega is None:
            raise PedidoSemEntregaAtrasada(pedido_id)
        cobranca = CobrancaEntrega(
            id=uuid4(),
            pedido_id=pedido_id,
            fornecedor_id=entrega.fornecedor_id,
            nova_previsao=nova_previsao,
            comentario=_opcional(comentario),
            cobrado_por=autor.nome,
            usuario_id=autor.id,
            criado_em=agora,
        )
        self._cobrancas.gravar(cobranca)
        return cobranca

    def entregas_do_sku(self, sku_code: str) -> list[EntregaPendente]:
        """O que ainda falta chegar do SKU, pela data prevista, com as cobranças de cada
        pedido. Lança `SKUNaoEncontrado`."""
        self._sku(sku_code)
        agora = self._relogio()
        entregas: list[EntregaPendente] = []
        for item in self._inventory.em_transito(sku_code).itens:
            cobrancas = self._cobrancas.listar(item.pedido_id)
            entregas.append(
                EntregaPendente(
                    pedido_id=item.pedido_id,
                    fornecedor_nome=item.fornecedor_nome,
                    status=item.status,
                    quantidade_pendente=item.quantidade_pendente,
                    data_prevista_entrega=item.data_prevista_entrega,
                    dias_de_atraso=dias_de_atraso(item.data_prevista_entrega, agora.date()),
                    cobranca_vigente=_cobranca_vigente(cobrancas[0] if cobrancas else None, agora),
                    cobrancas=cobrancas,
                )
            )
        return entregas

    def avisos_abertos(self, sku_code: str) -> list[Aviso]:
        """Os sem decisão de compra posterior, do mais recente para o mais antigo."""
        decisoes = self._decisoes.listar(sku_code)
        return _abertos(self._avisos.listar(sku_code), decisoes[0] if decisoes else None)

    def decisoes(self, sku_code: str) -> list[DecisaoCompra]:
        """Da mais recente para a mais antiga."""
        return self._decisoes.listar(sku_code)

    def painel(self, filtro: FiltroPainel | None = None) -> PainelDeAlertas:
        """Os SKUs ativos com decisão vigente vão para `decididos` (a decisão mais recente
        primeiro), para o comprador acompanhar o que decidiu. Os outros com aviso aberto ou
        algum motivo de alerta da política ativa vão para `alertas`, na ordem do painel. Um
        SKU sem estoque no ERP vai para `skus_com_erro` sem derrubar o painel.

        Um SKU tem o motivo `entrega_atrasada` com alguma entrega atrasada de pedido sem
        cobrança vigente. `entregas_atrasadas` agrupa por fornecedor essas entregas dos SKUs
        que ficaram nos alertas.

        O `filtro` vale para os alertas e os decididos, menos o motivo, que só vale para os
        alertas. `skus_com_erro` não é filtrado."""
        filtro = filtro or FiltroPainel()
        palavras = palavras_da_busca(filtro.busca or "")
        parametros = self._politicas.ativa().parametros
        agora = self._relogio()
        ultimas = self._decisoes.ultimas()
        avisos: dict[str, list[Aviso]] = {}
        for aviso in self._avisos.listar():
            avisos.setdefault(aviso.sku_code, []).append(aviso)

        retrato = self._ficha_sku.retrato()
        sugestoes = self._purchasing.sugerir_pedidos(retrato)
        cobrancas = self._cobrancas.ultimas()
        atrasadas: dict[str, list[EntregaAtrasada]] = {}
        if MotivoAlerta.ENTREGA_ATRASADA in parametros.motivos_de_alerta:
            for entrega in self._inventory.entregas_atrasadas(agora):
                if not _cobranca_vigente(cobrancas.get(entrega.pedido_id), agora):
                    atrasadas.setdefault(entrega.sku_code, []).append(entrega)

        alertas: list[ItemAlerta] = []
        decididos: list[ItemDecidido] = []
        com_erro: list[str] = []
        for sku in retrato.skus:
            ultima = ultimas.get(sku.sku_code)
            abertos = _abertos(avisos.get(sku.sku_code, []), ultima)
            vigente = _vigente(ultima, abertos, agora)
            ficha = retrato.fichas.get(sku.sku_code)
            if vigente is not None:
                if _passa_no_sku(filtro, palavras, sku, ficha):
                    decididos.append(ItemDecidido(sku=sku, decisao=vigente))
                continue
            if ficha is None:
                com_erro.append(sku.sku_code)
                continue
            if not _passa_no_sku(filtro, palavras, sku, ficha):
                continue
            item = _item(ficha, sugestoes[sku.sku_code], parametros, abertos, sku.sku_code in atrasadas)
            if (item.motivos or item.avisos_abertos) and _tem_o_motivo(filtro, item):
                alertas.append(item)
        decididos.sort(key=lambda d: (d.decisao.criado_em, d.sku.sku_code), reverse=True)
        entregas = [
            entrega
            for item in alertas
            if MotivoAlerta.ENTREGA_ATRASADA in item.motivos
            for entrega in atrasadas[item.sku.sku_code]
        ]
        return PainelDeAlertas(
            alertas=sorted(alertas, key=_ordem),
            decididos=decididos,
            skus_com_erro=com_erro,
            entregas_atrasadas=_por_fornecedor(entregas, retrato.fichas, parametros, cobrancas),
        )

    def varrer_episodios(self) -> None:
        """Abre e fecha os episódios de ruptura (por SKU) e de entrega atrasada (por pedido)
        pelas condições de agora, com o mesmo retrato em lote do painel. Com o motivo
        desligado na política, a condição não vale e os episódios dela fecham."""
        parametros = self._politicas.ativa().parametros
        agora = self._relogio()
        condicoes: list[Condicao] = []
        if MotivoAlerta.ABAIXO_DO_PISO_ALERTA in parametros.motivos_de_alerta:
            condicoes += self._condicoes_de_ruptura(parametros, agora)
        if MotivoAlerta.ENTREGA_ATRASADA in parametros.motivos_de_alerta:
            condicoes += self._condicoes_de_entrega(agora)
        self._notificacoes.varrer(TIPOS_DE_EPISODIO, condicoes)

    def _condicoes_de_ruptura(self, parametros: ParametrosPolitica, agora: datetime) -> list[Condicao]:
        ultimas = self._decisoes.ultimas()
        avisos: dict[str, list[Aviso]] = {}
        for aviso in self._avisos.listar():
            avisos.setdefault(aviso.sku_code, []).append(aviso)
        retrato = self._ficha_sku.retrato()
        condicoes: list[Condicao] = []
        for sku in retrato.skus:
            ficha = retrato.fichas.get(sku.sku_code)
            if ficha is None or not _em_ruptura(ficha.cobertura, parametros):
                continue
            ultima = ultimas.get(sku.sku_code)
            if _vigente(ultima, _abertos(avisos.get(sku.sku_code, []), ultima), agora) is not None:
                continue
            meses = ficha.cobertura.meses
            condicoes.append(
                Condicao(
                    tipo="ruptura",
                    sku_code=sku.sku_code,
                    papel_destino="comprador",
                    detalhe={
                        **_nome_do_sku(sku),
                        "disponivel": ficha.estoque.quantidade_disponivel,
                        "cobertura_dias": None if meses is None else dias_de_cobertura(meses),
                    },
                )
            )
        return condicoes

    def _condicoes_de_entrega(self, agora: datetime) -> list[Condicao]:
        cobrancas = self._cobrancas.ultimas()
        por_pedido: dict[UUID, list[EntregaAtrasada]] = {}
        for entrega in self._inventory.entregas_atrasadas(agora):
            if not _cobranca_vigente(cobrancas.get(entrega.pedido_id), agora):
                por_pedido.setdefault(entrega.pedido_id, []).append(entrega)
        return [
            Condicao(
                tipo="entrega_atrasada",
                pedido_id=pedido_id,
                papel_destino="comprador",
                detalhe={
                    "fornecedor_nome": entregas[0].fornecedor_nome,
                    "data_prevista_entrega": entregas[0].data_prevista_entrega.isoformat(),
                    "dias_de_atraso": entregas[0].dias_de_atraso,
                    "skus": sorted(e.sku_code for e in entregas),
                },
            )
            for pedido_id, entregas in por_pedido.items()
        ]

    def estoque(
        self, filtro: FiltroEstoque, ordem: OrdemEstoque = "cobertura", pagina: int = 1, por_pagina: int = 50
    ) -> PaginaDeEstoque:
        """Os SKUs ativos com estoque no ERP, do retrato em lote, com o filtro aplicado. Por
        `cobertura` (a menor primeiro, os sem giro no fim), `venda_diaria` (a maior primeiro)
        ou `nome` (produto, cor e tamanho), com o código para desempatar. Ruptura é a
        cobertura abaixo do piso de alerta da política ativa, com ou sem o motivo ligado.
        Página depois da última vem vazia, com o total."""
        palavras = palavras_da_busca(filtro.busca or "")
        parametros = self._politicas.ativa().parametros
        retrato = self._ficha_sku.retrato()
        fichas = [
            ficha
            for sku in retrato.skus
            if (ficha := retrato.fichas.get(sku.sku_code)) is not None
            and _passa_no_estoque(filtro, palavras, ficha, parametros)
        ]
        fichas.sort(key=ORDENS_DO_ESTOQUE[ordem])
        inicio = (pagina - 1) * por_pagina
        return PaginaDeEstoque(
            itens=[_item_de_estoque(f, parametros) for f in fichas[inicio : inicio + por_pagina]],
            total=len(fichas),
            pagina=pagina,
            por_pagina=por_pagina,
        )
