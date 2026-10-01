"""Módulo `aprovacao`: a fila de aprovação das sugestões de pedido e a decisão humana.

Gera as sugestões de todos os SKUs ativos, guarda na fila as que têm compra, com os
sinais do corpus e a faixa de aprovação, e registra a decisão do comprador chefe.
Aprovar é o único caminho até `purchasing.submeter_pedido` (`module-interfaces.md`).
Os motivos de destaque, escolhidos pelo comprador na política de compra, só ordenam
a fila, nunca aprovam.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.ai.decisao import DecisaoIndisponivel
from src.ai.schemas import SinaisDasSugestoes, SinalCorpus, SugestaoComSinais
from src.ai.sinais import SinaisCorpus
from src.aprovacao.repositorio import SugestoesFilaRepositorio
from src.aprovacao.schemas import ResultadoGeracao, StatusSugestao, SugestaoNaFila
from src.catalog.schemas import SKU
from src.catalog.service import Catalog
from src.purchasing.schemas import FaixaAprovacao, SugestaoPedido
from src.purchasing.service import Purchasing


class SugestaoNaoEncontrada(LookupError):
    def __init__(self, id: UUID) -> None:
        super().__init__(f"Sugestão {id} não encontrada na fila.")
        self.id = id


class SugestaoJaDecidida(Exception):
    def __init__(self, id: UUID, status: StatusSugestao) -> None:
        super().__init__(f"A sugestão {id} não está mais pendente (está {status}).")
        self.id = id
        self.status = status


class JustificativaObrigatoria(ValueError):
    def __init__(self, faixa: FaixaAprovacao) -> None:
        super().__init__(
            f"O pedido fica na faixa {faixa.faixa} ({faixa.aprovadores}) e exige justificativa."
        )
        self.faixa = faixa


def _obrigatorio(valor: str, campo: str) -> str:
    valor = valor.strip()
    if not valor:
        raise ValueError(f"{campo} não pode ser vazio")
    return valor


def _destaque(sugestao: SugestaoPedido, sinais: list[SinalCorpus] | None, motivos: Iterable[str]) -> bool:
    """Se a sugestão tem algum alerta ou sinal entre os motivos de destaque da política."""
    ocorridos = {a.tipo.value for a in sugestao.alertas} | {s.tipo for s in sinais or []}
    return not ocorridos.isdisjoint(motivos)


def _conferir_pendente(sugestao: SugestaoNaFila) -> None:
    if sugestao.status != "pendente":
        raise SugestaoJaDecidida(sugestao.id, sugestao.status)


class Aprovacao:
    def __init__(
        self,
        catalog: Catalog,
        purchasing: Purchasing,
        fila: SugestoesFilaRepositorio,
        *,
        now: datetime | None = None,
    ) -> None:
        self._catalog = catalog
        self._purchasing = purchasing
        self._fila = fila
        self._now = now

    def _agora(self) -> datetime:
        return self._now or datetime.now(UTC)

    def gerar_fila(self, sinais: SinaisCorpus) -> ResultadoGeracao:
        """Sugestão para cada SKU ativo; as com compra entram na fila no lugar de todas
        as pendentes anteriores. `sinais` vem na chamada porque só a geração precisa do
        modelo de decisão. Com ele fora do ar, as sugestões entram sem sinais.
        Propaga `SKUSemEstoque`."""
        skus = self._catalog.listar_skus()
        pares: list[tuple[SugestaoPedido, SKU]] = []
        for sku in skus:
            sugestao = self._purchasing.sugerir_pedido(sku.sku_code)
            if sugestao is not None and sugestao.quantidade > 0:
                pares.append((sugestao, sku))

        calculados: SinaisDasSugestoes | None
        try:
            calculados = sinais.para_sugestoes(pares)
        except DecisaoIndisponivel:
            calculados = None

        agora = self._agora()
        novas = [
            self._na_fila(sugestao, sku, None if calculados is None else calculados.por_sku[sku.sku_code], agora)
            for sugestao, sku in pares
        ]
        substituidas = self._fila.substituir_pendentes(novas)
        return ResultadoGeracao(
            geradas=len(novas),
            substituidas=substituidas,
            skus_avaliados=len(skus),
            sinais_indisponiveis=calculados is None,
        )

    def _na_fila(
        self, sugestao: SugestaoPedido, sku: SKU, sinais: list[SinalCorpus] | None, agora: datetime
    ) -> SugestaoNaFila:
        return SugestaoNaFila(
            id=uuid4(),
            criado_em=agora,
            status="pendente",
            destaque=_destaque(
                sugestao, sinais, self._purchasing.politica_da(sugestao).parametros.motivos_de_destaque
            ),
            sku=sku,
            sugestao=SugestaoComSinais(sugestao=sugestao, sinais=sinais),
            faixa=self._purchasing.faixa_aprovacao(sugestao),
        )

    def listar(self, status: StatusSugestao = "pendente") -> list[SugestaoNaFila]:
        """Pendentes na ordem da fila; as outras, da decisão mais recente para a mais antiga."""
        return self._fila.listar(status)

    def carregar(self, id: UUID) -> SugestaoNaFila | None:
        return self._fila.carregar(id)

    def faixa_para(self, id: UUID, quantidade: int) -> FaixaAprovacao:
        """Faixa que a aprovação teria com esta quantidade, para o comprador saber antes de
        aprovar se ela exige justificativa. Lança `SugestaoNaoEncontrada` e
        `QuantidadeInvalida`."""
        na_fila = self._fila.carregar(id)
        if na_fila is None:
            raise SugestaoNaoEncontrada(id)
        return self._purchasing.faixa_aprovacao(na_fila.sugestao.sugestao, quantidade)

    def _decidir(self, id: UUID, decisao: Callable[[SugestaoNaFila], SugestaoNaFila]) -> SugestaoNaFila:
        decidida = self._fila.decidir(id, decisao)
        if decidida is None:
            raise SugestaoNaoEncontrada(id)
        return decidida

    def aprovar(
        self,
        id: UUID,
        aprovado_por: str,
        quantidade: int | None = None,
        justificativa: str | None = None,
    ) -> SugestaoNaFila:
        """Cria o pedido de compra no ERP com a quantidade sugerida ou a editada, com a
        sugestão reservada na fila: uma segunda aprovação simultânea espera e recebe
        `SugestaoJaDecidida` sem criar pedido, e uma falha do ERP solta a reserva. A
        faixa é recalculada com essa quantidade e a versão da política da sugestão.
        Lança `SugestaoNaoEncontrada`, `SugestaoJaDecidida`, `QuantidadeInvalida` (zero
        ou abaixo do MOQ), `JustificativaObrigatoria` e `ValueError` sem `aprovado_por`."""
        aprovado_por = _obrigatorio(aprovado_por, "aprovado_por")
        justificativa = (justificativa or "").strip() or None

        def aprovada(na_fila: SugestaoNaFila) -> SugestaoNaFila:
            _conferir_pendente(na_fila)
            sugestao = na_fila.sugestao.sugestao
            quantidade_aprovada = sugestao.quantidade if quantidade is None else quantidade
            faixa = self._purchasing.faixa_aprovacao(sugestao, quantidade_aprovada)
            if faixa.exige_justificativa and justificativa is None:
                raise JustificativaObrigatoria(faixa)
            pedido_compra_id = self._purchasing.submeter_pedido(
                sugestao, quantidade_aprovada, aprovado_por, str(id)
            )
            return na_fila.model_copy(
                update={
                    "status": "aprovada",
                    "faixa": faixa,
                    "decidido_em": self._agora(),
                    "decidido_por": aprovado_por,
                    "quantidade_aprovada": quantidade_aprovada,
                    "justificativa": justificativa,
                    "pedido_compra_id": pedido_compra_id,
                }
            )

        return self._decidir(id, aprovada)

    def rejeitar(self, id: UUID, rejeitado_por: str, motivo: str) -> SugestaoNaFila:
        """Lança `SugestaoNaoEncontrada`, `SugestaoJaDecidida` e `ValueError` sem
        `rejeitado_por` ou sem `motivo`."""
        rejeitado_por = _obrigatorio(rejeitado_por, "rejeitado_por")
        motivo = _obrigatorio(motivo, "motivo")

        def rejeitada(na_fila: SugestaoNaFila) -> SugestaoNaFila:
            _conferir_pendente(na_fila)
            return na_fila.model_copy(
                update={
                    "status": "rejeitada",
                    "decidido_em": self._agora(),
                    "decidido_por": rejeitado_por,
                    "motivo_rejeicao": motivo,
                }
            )

        return self._decidir(id, rejeitada)
