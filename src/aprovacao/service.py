"""Módulo `aprovacao`: a fila de aprovação das sugestões de pedido e a decisão humana.

Gera as sugestões de todos os SKUs ativos, guarda na fila as que têm compra, com os
sinais do corpus e a faixa de aprovação, e registra a decisão do comprador chefe.
Aprovar é o único caminho até `purchasing.submeter_pedido` (`module-interfaces.md`).
Os alertas de risco e os sinais só ordenam a fila, nunca aprovam.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.ai.decisao import DecisaoIndisponivel
from src.ai.schemas import SinaisDasSugestoes, SinalCorpus, SugestaoComSinais
from src.ai.sinais import SinaisCorpus
from src.aprovacao.repositorio import SugestoesFila
from src.aprovacao.schemas import ResultadoGeracao, StatusSugestao, SugestaoNaFila
from src.catalog.schemas import SKU
from src.catalog.service import Catalog
from src.purchasing.schemas import FaixaAprovacao, SugestaoPedido, TipoAlerta
from src.purchasing.service import Purchasing

ALERTAS_DE_DESTAQUE = frozenset(
    {
        TipoAlerta.RUPTURA_ANTES_DA_CHEGADA,
        TipoAlerta.VIOLA_TETO,
        TipoAlerta.LEAD_TIME_OBSERVADO_ACIMA_DO_CONTRATADO,
    }
)


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


def _destaque(sugestao: SugestaoPedido, sinais: list[SinalCorpus] | None) -> bool:
    return bool(sinais) or any(a.tipo in ALERTAS_DE_DESTAQUE for a in sugestao.alertas)


class Aprovacao:
    def __init__(
        self,
        catalog: Catalog,
        purchasing: Purchasing,
        fila: SugestoesFila,
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
            destaque=_destaque(sugestao, sinais),
            sku=sku,
            sugestao=SugestaoComSinais(sugestao=sugestao, sinais=sinais),
            faixa=self._purchasing.faixa_aprovacao(sugestao),
        )

    def listar(self, status: StatusSugestao = "pendente") -> list[SugestaoNaFila]:
        """Pendentes na ordem da fila; as outras, da decisão mais recente para a mais antiga."""
        return self._fila.listar(status)

    def carregar(self, id: UUID) -> SugestaoNaFila | None:
        return self._fila.carregar(id)

    def _pendente(self, id: UUID) -> SugestaoNaFila:
        sugestao = self._fila.carregar(id)
        if sugestao is None:
            raise SugestaoNaoEncontrada(id)
        if sugestao.status != "pendente":
            raise SugestaoJaDecidida(id, sugestao.status)
        return sugestao

    def _registrar(self, decidida: SugestaoNaFila) -> SugestaoNaFila:
        """Outra decisão pode ter chegado entre a leitura e a gravação."""
        if self._fila.registrar_decisao(decidida):
            return decidida
        atual = self._fila.carregar(decidida.id)
        if atual is None:
            raise SugestaoNaoEncontrada(decidida.id)
        raise SugestaoJaDecidida(decidida.id, atual.status)

    def aprovar(
        self,
        id: UUID,
        aprovado_por: str,
        quantidade: int | None = None,
        justificativa: str | None = None,
    ) -> SugestaoNaFila:
        """Cria o pedido de compra no ERP com a quantidade sugerida ou a editada. A faixa
        é recalculada com essa quantidade e a política em vigor. Lança
        `SugestaoNaoEncontrada`, `SugestaoJaDecidida`, `QuantidadeInvalida` (zero ou
        abaixo do MOQ), `JustificativaObrigatoria` e `ValueError` sem `aprovado_por`."""
        na_fila = self._pendente(id)
        aprovado_por = _obrigatorio(aprovado_por, "aprovado_por")
        sugestao = na_fila.sugestao.sugestao
        quantidade = sugestao.quantidade if quantidade is None else quantidade
        faixa = self._purchasing.faixa_aprovacao(sugestao, quantidade)
        justificativa = (justificativa or "").strip() or None
        if faixa.exige_justificativa and justificativa is None:
            raise JustificativaObrigatoria(faixa)
        pedido_compra_id = self._purchasing.submeter_pedido(sugestao, quantidade, aprovado_por, str(id))
        return self._registrar(
            na_fila.model_copy(
                update={
                    "status": "aprovada",
                    "faixa": faixa,
                    "decidido_em": self._agora(),
                    "decidido_por": aprovado_por,
                    "quantidade_aprovada": quantidade,
                    "justificativa": justificativa,
                    "pedido_compra_id": pedido_compra_id,
                }
            )
        )

    def rejeitar(self, id: UUID, rejeitado_por: str, motivo: str) -> SugestaoNaFila:
        """Lança `SugestaoNaoEncontrada`, `SugestaoJaDecidida` e `ValueError` sem
        `rejeitado_por` ou sem `motivo`."""
        na_fila = self._pendente(id)
        return self._registrar(
            na_fila.model_copy(
                update={
                    "status": "rejeitada",
                    "decidido_em": self._agora(),
                    "decidido_por": _obrigatorio(rejeitado_por, "rejeitado_por"),
                    "motivo_rejeicao": _obrigatorio(motivo, "motivo"),
                }
            )
        )
