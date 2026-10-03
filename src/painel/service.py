"""Módulo `painel`: o painel de alertas do comprador chefe, os avisos da equipe de
vendas e as decisões de compra (ADR-0005).

O painel é calculado na hora, sem estado próprio, a partir da sugestão de pedido de
cada SKU ativo com a política ativa, dos avisos abertos e da decisão vigente. Não
chama o Jev: os sinais do corpus ficam na tela do SKU.

Aviso aberto é o que não tem decisão de compra do mesmo SKU registrada depois dele.
Decisão vigente é a mais recente do SKU, com menos de `PRAZO_DA_DECISAO` e sem aviso
posterior. Nada é atualizado: as duas coisas saem das datas.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.catalog.schemas import SKU
from src.catalog.service import Catalog
from src.ficha_sku.service import SKUSemEstoque
from src.inventory.schemas import Cobertura
from src.inventory.service import Inventory
from src.painel.repositorio import AvisosRepositorio, DecisoesRepositorio
from src.painel.schemas import (
    Aviso,
    DecisaoCompra,
    ItemAlerta,
    ItemDecidido,
    PainelDeAlertas,
    TipoAviso,
    TipoDecisao,
)
from src.politica_compra.repositorio import PoliticaCompraRepositorio
from src.politica_compra.schemas import DIAS_POR_MES, MotivoAlerta, ParametrosPolitica
from src.purchasing.schemas import SugestaoPedido
from src.purchasing.service import Purchasing

Relogio = Callable[[], datetime]

PRAZO_DA_DECISAO = timedelta(days=7)


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


def _obrigatorio(valor: str, campo: str) -> str:
    valor = valor.strip()
    if not valor:
        raise ValueError(f"{campo} não pode ser vazio")
    return valor


def _opcional(valor: str | None) -> str | None:
    return (valor or "").strip() or None


def _motivos(
    sugestao: SugestaoPedido, cobertura: Cobertura, parametros: ParametrosPolitica
) -> list[MotivoAlerta]:
    """Os alertas da sugestão e o piso de alerta, filtrados pelos motivos de alerta da política."""
    ocorridos = [MotivoAlerta(a.tipo.value) for a in sugestao.alertas]
    if cobertura.meses is not None and cobertura.meses < parametros.piso_alerta_dias / DIAS_POR_MES:
        ocorridos.append(MotivoAlerta.ABAIXO_DO_PISO_ALERTA)
    return [m for m in ocorridos if m in parametros.motivos_de_alerta]


def _abertos(avisos: list[Aviso], ultima: DecisaoCompra | None) -> list[Aviso]:
    return [a for a in avisos if ultima is None or a.criado_em > ultima.criado_em]


def _vigente(ultima: DecisaoCompra | None, abertos: list[Aviso], agora: datetime) -> DecisaoCompra | None:
    if ultima is None or abertos or agora - ultima.criado_em >= PRAZO_DA_DECISAO:
        return None
    return ultima


def _grupo(item: ItemAlerta) -> int:
    """Os grupos do painel, na ordem: aviso aberto, ruptura, ruptura antes da chegada e
    os outros motivos."""
    if item.avisos_abertos:
        return 0
    if MotivoAlerta.ABAIXO_DO_PISO_ALERTA in item.motivos:
        return 1
    if MotivoAlerta.RUPTURA_ANTES_DA_CHEGADA in item.motivos:
        return 2
    return 3


def _ordem(item: ItemAlerta) -> tuple[int, bool, bool, float, str]:
    """Pelo grupo; em cada grupo, disponível zero no topo, depois a menor cobertura atual,
    os sem giro no fim e o código para desempatar."""
    cobertura = item.cobertura_atual_meses
    return (_grupo(item), item.disponivel > 0, cobertura is None, cobertura or 0.0, item.sku.sku_code)


class Painel:
    def __init__(
        self,
        catalog: Catalog,
        inventory: Inventory,
        purchasing: Purchasing,
        politicas: PoliticaCompraRepositorio,
        avisos: AvisosRepositorio,
        decisoes: DecisoesRepositorio,
        *,
        relogio: Relogio = agora_utc,
    ) -> None:
        self._catalog = catalog
        self._inventory = inventory
        self._purchasing = purchasing
        self._politicas = politicas
        self._avisos = avisos
        self._decisoes = decisoes
        self._relogio = relogio

    def _sku(self, sku_code: str) -> SKU:
        sku = self._catalog.carregar_sku(sku_code)
        if sku is None:
            raise SKUNaoEncontrado(sku_code)
        return sku

    def registrar_aviso(
        self, sku_code: str, tipo: TipoAviso, avisado_por: str, comentario: str | None = None
    ) -> Aviso:
        """Lança `SKUNaoEncontrado`, `SKUInativo` e `ValueError` sem `avisado_por`."""
        avisado_por = _obrigatorio(avisado_por, "avisado_por")
        sku = self._sku(sku_code)
        if not sku.ativo:
            raise SKUInativo(sku_code)
        aviso = Aviso(
            id=uuid4(),
            sku_code=sku_code,
            tipo=tipo,
            comentario=_opcional(comentario),
            avisado_por=avisado_por,
            criado_em=self._relogio(),
        )
        self._avisos.gravar(aviso)
        return aviso

    def registrar_decisao(
        self,
        sku_code: str,
        tipo: TipoDecisao,
        decidido_por: str,
        quantidade: int | None = None,
        motivo: str | None = None,
        comentario: str | None = None,
    ) -> DecisaoCompra:
        """Guarda a sugestão de pedido do momento (quantidade e versão da política). Fecha
        os avisos abertos do SKU e o tira do painel por `PRAZO_DA_DECISAO`. Não cria pedido
        de compra. Lança `SKUNaoEncontrado`, `QuantidadeObrigatoria`,
        `QuantidadeSoParaComprar`, `MotivoObrigatorio` e `ValueError` sem `decidido_por`.
        Propaga `SKUSemEstoque`."""
        decidido_por = _obrigatorio(decidido_por, "decidido_por")
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
            decidido_por=decidido_por,
            quantidade_sugerida=sugestao.quantidade,
            politica_versao=sugestao.politica_versao,
            criado_em=self._relogio(),
        )
        self._decisoes.gravar(decisao)
        return decisao

    def avisos_abertos(self, sku_code: str) -> list[Aviso]:
        """Os sem decisão de compra posterior, do mais recente para o mais antigo."""
        decisoes = self._decisoes.listar(sku_code)
        return _abertos(self._avisos.listar(sku_code), decisoes[0] if decisoes else None)

    def decisoes(self, sku_code: str) -> list[DecisaoCompra]:
        """Da mais recente para a mais antiga."""
        return self._decisoes.listar(sku_code)

    def painel(self) -> PainelDeAlertas:
        """Os SKUs ativos com decisão vigente vão para `decididos` (a decisão mais recente
        primeiro), para o comprador acompanhar o que decidiu. Os outros com aviso aberto ou
        algum motivo de alerta da política ativa vão para `alertas`, na ordem do painel. Um
        SKU sem estoque no ERP vai para `skus_com_erro` sem derrubar o painel."""
        parametros = self._politicas.ativa().parametros
        agora = self._relogio()
        ultimas = self._decisoes.ultimas()
        avisos: dict[str, list[Aviso]] = {}
        for aviso in self._avisos.listar():
            avisos.setdefault(aviso.sku_code, []).append(aviso)

        alertas: list[ItemAlerta] = []
        decididos: list[ItemDecidido] = []
        com_erro: list[str] = []
        for sku in self._catalog.listar_skus():
            ultima = ultimas.get(sku.sku_code)
            abertos = _abertos(avisos.get(sku.sku_code, []), ultima)
            vigente = _vigente(ultima, abertos, agora)
            if vigente is not None:
                decididos.append(ItemDecidido(sku=sku, decisao=vigente))
                continue
            try:
                item = self._item(sku, parametros, abertos)
            except SKUSemEstoque:
                com_erro.append(sku.sku_code)
                continue
            if item is not None and (item.motivos or item.avisos_abertos):
                alertas.append(item)
        decididos.sort(key=lambda d: (d.decisao.criado_em, d.sku.sku_code), reverse=True)
        return PainelDeAlertas(alertas=sorted(alertas, key=_ordem), decididos=decididos, skus_com_erro=com_erro)

    def _item(self, sku: SKU, parametros: ParametrosPolitica, avisos: list[Aviso]) -> ItemAlerta | None:
        sugestao = self._purchasing.sugerir_pedido(sku.sku_code)
        estoque = self._inventory.estoque_atual(sku.sku_code)
        if sugestao is None or estoque is None:
            return None
        cobertura = self._inventory.cobertura_meses(sku.sku_code)
        fornecedor = sugestao.fornecedor if sugestao.quantidade > 0 else None
        return ItemAlerta(
            sku=sku,
            disponivel=estoque.quantidade_disponivel,
            cobertura_atual_meses=cobertura.meses,
            cobertura_na_chegada_sem_compra_meses=(
                sugestao.calculo.cobertura_na_chegada_sem_compra_meses if sugestao.calculo else None
            ),
            motivos=_motivos(sugestao, cobertura, parametros),
            quantidade_sugerida=sugestao.quantidade if fornecedor else None,
            fornecedor_sugerido=fornecedor.fornecedor_nome if fornecedor else None,
            avisos_abertos=avisos,
        )
