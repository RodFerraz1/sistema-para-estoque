"""Chat do Copilot (ADR-0002): o Jev entende a pergunta, o código roteia pela faixa
de confiança e monta os dados, e o redator só escreve a resposta.

Esclarecimento e fora de escopo são respostas feitas em código, sem redator. A
sugestão de compra leva os sinais do corpus de cada sugestão, e toda resposta
redigida por LLM tem as citações conferidas pelo Jev e marcadas quando não são
confirmadas.
"""
from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import get_args
from uuid import UUID, uuid4

from src.ai.busca import BuscaContexto
from src.ai.citacoes import conferir_citacoes, decidir_vereditos, extrair_citacoes, marcar_citacoes
from src.ai.contexto import renderizar_contexto
from src.ai.decisao import DecisaoIndisponivel, DecisionModel
from src.ai.identificacao import identificar_skus, produtos_do_catalogo
from src.ai.redator import LLM_INDISPONIVEL, Redator, RedatorIndisponivel, RedatorSemLLM
from src.ai.registro import RegistrosDecisao
from src.ai.schemas import (
    Acao,
    ConflitoEntreTrechos,
    Entendimento,
    Faixa,
    Identificacao,
    Intencao,
    Montagem,
    ProdutoCatalogo,
    RegistroDecisao,
    RespostaCopilot,
    SinaisDasSugestoes,
    SinaisDoSKU,
    SugestaoComSinais,
    Trecho,
    TrechoClassificado,
    VerificacaoCitacao,
)
from src.ai.sinais import SinaisCorpus
from src.catalog.service import Catalog
from src.ficha_sku.service import FichaSKU, SKUSemEstoque
from src.politica_compra.repositorio import PoliticaCompraRepositorio
from src.purchasing.schemas import SugestaoPedido
from src.purchasing.service import Purchasing

@dataclass(frozen=True)
class FaixasConfianca:
    """Partem do spike do M4 (acertos de 0,64 a 1,00, erro em 0,36) e do piso de 0,5
    da doc do Jev. Recalibrar com o registro de decisão é tarefa do M8."""

    alta: float
    media: float


FAIXAS = FaixasConfianca(alta=0.80, media=0.50)
MAX_TRECHOS_NO_CONTEXTO = 10

DESCRICOES_INTENCAO: dict[Intencao, str] = {
    "situacao_sku": "ver a situação de um SKU (estoque, giro e cobertura)",
    "sugestao_compra": "uma sugestão de compra",
    "politica_ou_fornecedor": "saber da política de compra e dos fornecedores",
    "fora_de_escopo": "algo fora das compras",
}
RESPOSTA_FORA_DE_ESCOPO = (
    "Só consigo ajudar com as compras do atacadista: situação de SKU, sugestão de pedido, "
    "política de compra e fornecedores."
)
ESCLARECIMENTO_DE_SKU = (
    "Não identifiquei o produto no catálogo. Informe o código do SKU (ex: TBC-BEGE-70140-01) "
    "ou o nome do produto."
)
OBSERVACAO_SUGESTAO_SEM_SKU = (
    "Nenhum SKU do catálogo foi identificado na pergunta: a quantidade da sugestão depende de um "
    "SKU do catálogo (código, ou nome do produto com cor e tamanho)."
)
AVISO_SEM_SINAIS = "Observação: não consegui calcular os sinais do corpus agora, então a sugestão vem sem eles."
AVISO_SEM_VERIFICACAO = (
    "Observação: não consegui verificar as citações agora, então elas vêm marcadas como não confirmadas."
)


@dataclass(frozen=True)
class _Dados:
    """A montagem que vai ao redator, os trechos que ele pode citar (os do contexto e
    os de origem dos sinais que não couberam nele, cujos ids aparecem nos sinais) e os
    avisos que o código acrescenta ao fim da resposta."""

    montagem: Montagem
    citaveis: list[Trecho]
    avisos: list[str]


class Copilot:
    def __init__(
        self,
        decisao: DecisionModel,
        catalog: Catalog,
        ficha_sku: FichaSKU,
        purchasing: Purchasing,
        politicas: PoliticaCompraRepositorio,
        busca: BuscaContexto,
        sinais: SinaisCorpus,
        redator: Redator,
        registros: RegistrosDecisao,
    ) -> None:
        self._decisao = decisao
        self._catalog = catalog
        self._ficha_sku = ficha_sku
        self._purchasing = purchasing
        self._politicas = politicas
        self._busca = busca
        self._sinais = sinais
        self._redator = redator
        self._registros = registros

    def responder(self, pergunta: str) -> RespostaCopilot:
        """Grava um registro de decisão por resposta. Propaga `DecisaoIndisponivel`
        (sem entendimento não há roteamento nem registro) e a falha ao gravar
        (o registro é requisito de auditoria)."""
        inicio = time.perf_counter()
        resposta = self._decidir(pergunta, uuid4())
        duracao_ms = round((time.perf_counter() - inicio) * 1000)
        self._registros.gravar(_registro(pergunta, resposta, duracao_ms))
        return resposta

    def _decidir(self, pergunta: str, registro_id: UUID) -> RespostaCopilot:
        produtos = produtos_do_catalogo(self._catalog.listar_skus())
        entendimento = self._decisao.entender_pergunta(pergunta, produtos)
        faixa = _faixa(entendimento.intencao.confianca)
        intencao = entendimento.intencao.escolha

        def resposta_copilot(
            texto: str,
            acao: Acao,
            identificacao: Identificacao | None = None,
            montagem: Montagem = Montagem(),
            redator: str | None = None,
            citacoes: Sequence[VerificacaoCitacao] = (),
        ) -> RespostaCopilot:
            return RespostaCopilot(
                resposta=texto,
                acao=acao,
                faixa=faixa,
                entendimento=entendimento,
                identificacao=identificacao,
                fichas=montagem.fichas,
                sugestoes=montagem.sugestoes,
                trechos=montagem.trechos,
                conflitos=montagem.conflitos,
                citacoes=list(citacoes),
                redator=redator,
                registro_id=registro_id,
            )

        if faixa == "baixa":
            return resposta_copilot(_esclarecimento_de_intencao(entendimento), "pediu_esclarecimento")
        if intencao == "fora_de_escopo":
            return resposta_copilot(RESPOSTA_FORA_DE_ESCOPO, "fora_de_escopo")

        identificacao = None
        if intencao in ("situacao_sku", "sugestao_compra"):
            identificacao = identificar_skus(pergunta, entendimento, produtos)
            if intencao == "situacao_sku" and not identificacao.skus:
                return resposta_copilot(
                    _esclarecimento_de_sku(identificacao.candidatos), "pediu_esclarecimento", identificacao
                )

        dados = self._montar(pergunta, intencao, identificacao, produtos)
        redacao, redator = self._redigir(pergunta, dados.montagem)
        citacoes: list[VerificacaoCitacao] = []
        avisos = dados.avisos
        if redator != RedatorSemLLM.nome:
            redacao, citacoes, avisos_da_verificacao = self._verificar(redacao, dados.citaveis)
            avisos = [*avisos, *avisos_da_verificacao]
        texto = "\n\n".join([redacao, *avisos])
        if faixa == "alta":
            return resposta_copilot(texto, "respondeu", identificacao, dados.montagem, redator, citacoes)
        return resposta_copilot(
            f"{_confirmacao(intencao)}\n\n{texto}",
            "confirmou_e_respondeu",
            identificacao,
            dados.montagem,
            redator,
            citacoes,
        )

    def _montar(
        self,
        pergunta: str,
        intencao: Intencao,
        identificacao: Identificacao | None,
        produtos: Sequence[ProdutoCatalogo],
    ) -> _Dados:
        skus = identificacao.skus if identificacao else []
        observacoes: list[str] = []
        if identificacao and identificacao.total_skus > len(skus):
            observacoes.append(
                f"A pergunta corresponde a {identificacao.total_skus} SKUs; "
                f"os dados abaixo trazem só os {len(skus)} primeiros."
            )

        if intencao == "situacao_sku":
            fichas = _por_sku(skus, self._ficha_sku.completa, observacoes)
            return _Dados(Montagem(fichas=fichas, politica=self._politicas.ativa(), observacoes=observacoes), [], [])

        if intencao == "sugestao_compra":
            if not skus:
                observacoes.append(OBSERVACAO_SUGESTAO_SEM_SKU)
            sugestoes = _por_sku(skus, self._purchasing.sugerir_pedido, observacoes)
            da_pergunta, conflitos = self._buscar(pergunta)
            sinais, avisos = self._calcular_sinais(sugestoes, produtos)
            ids = {t.id for t in da_pergunta}
            de_sinais = [t for t in sinais.trechos if t.id not in ids]
            montagem = Montagem(
                sugestoes=[SugestaoComSinais(sugestao=s, sinais=sinais.por_sku.get(s.sku_code, [])) for s in sugestoes],
                politica=self._politicas.ativa(),
                trechos=[*da_pergunta, *de_sinais][:MAX_TRECHOS_NO_CONTEXTO],
                conflitos=conflitos,
                observacoes=observacoes,
            )
            return _Dados(montagem, [*da_pergunta, *de_sinais], avisos)

        trechos, conflitos = self._buscar(pergunta)
        return _Dados(Montagem(trechos=trechos, conflitos=conflitos, observacoes=observacoes), trechos, [])

    def _calcular_sinais(
        self, sugestoes: Sequence[SugestaoPedido], produtos: Sequence[ProdutoCatalogo]
    ) -> tuple[SinaisDasSugestoes, list[str]]:
        """O Jev fora do ar nos sinais não derruba a resposta: ela sai sem sinais e com um aviso."""
        por_codigo = {sku.sku_code: sku for produto in produtos for sku in produto.skus}
        try:
            return self._sinais.para_sugestoes_com_trechos([(s, por_codigo[s.sku_code]) for s in sugestoes]), []
        except DecisaoIndisponivel:
            return SinaisDasSugestoes(por_sku={}, trechos=[]), [AVISO_SEM_SINAIS]

    def _verificar(
        self, redacao: str, citaveis: Sequence[Trecho]
    ) -> tuple[str, list[VerificacaoCitacao], list[str]]:
        """Verifica só a redação, antes da confirmação e dos avisos. O Jev fora do ar
        deixa as citações `incerta` (as inventadas continuam inventadas) e acrescenta um aviso."""
        try:
            verificacoes, avisos = conferir_citacoes(redacao, citaveis, self._decisao), []
        except DecisaoIndisponivel:
            ids = {t.id for t in citaveis}
            verificacoes, avisos = decidir_vereditos(extrair_citacoes(redacao), ids, []), [AVISO_SEM_VERIFICACAO]
        return marcar_citacoes(redacao, verificacoes), verificacoes, avisos

    def _buscar(self, pergunta: str) -> tuple[list[TrechoClassificado], list[ConflitoEntreTrechos]]:
        resultado = self._busca.buscar(pergunta)
        trechos = sorted(
            (t for t in resultado.trechos if t.classificacao != "descartado"),
            key=lambda t: (t.classificacao != "aceito", -t.similaridade),
        )[:MAX_TRECHOS_NO_CONTEXTO]
        ids = {t.id for t in trechos}
        conflitos = [c for c in resultado.conflitos if c.trecho_a in ids and c.trecho_b in ids]
        return trechos, conflitos

    def _redigir(self, pergunta: str, montagem: Montagem) -> tuple[str, str]:
        try:
            return self._redator.redigir(pergunta, renderizar_contexto(montagem)), self._redator.nome
        except RedatorIndisponivel:
            sem_llm = RedatorSemLLM(LLM_INDISPONIVEL)
            observacao = f"O redator {self._redator.nome} falhou; a resposta vai sem redação."
            montagem = montagem.model_copy(update={"observacoes": [*montagem.observacoes, observacao]})
            return sem_llm.redigir(pergunta, renderizar_contexto(montagem)), sem_llm.nome


def _registro(pergunta: str, resposta: RespostaCopilot, duracao_ms: int) -> RegistroDecisao:
    return RegistroDecisao(
        id=resposta.registro_id,
        criado_em=datetime.now(UTC),
        pergunta=pergunta,
        intencao=resposta.entendimento.intencao.escolha,
        confianca=resposta.entendimento.intencao.confianca,
        faixa=resposta.faixa,
        acao=resposta.acao,
        skus=resposta.identificacao.skus if resposta.identificacao else [],
        entendimento=resposta.entendimento,
        trechos=[t.id for t in resposta.trechos],
        redator=resposta.redator,
        resposta=resposta.resposta,
        duracao_ms=duracao_ms,
        sinais=[SinaisDoSKU(sku_code=s.sugestao.sku_code, sinais=s.sinais) for s in resposta.sugestoes if s.sinais],
        citacoes=resposta.citacoes,
    )


def _por_sku[T](skus: Sequence[str], ler: Callable[[str], T | None], observacoes: list[str]) -> list[T]:
    lidos: list[T] = []
    for sku in skus:
        try:
            lido = ler(sku)
        except SKUSemEstoque:
            observacoes.append(f"O SKU {sku} não tem registro de estoque no ERP.")
            continue
        if lido is not None:
            lidos.append(lido)
    return lidos


def _faixa(confianca: float) -> Faixa:
    if confianca >= FAIXAS.alta:
        return "alta"
    if confianca >= FAIXAS.media:
        return "media"
    return "baixa"


def _esclarecimento_de_intencao(entendimento: Entendimento) -> str:
    probabilidades = entendimento.intencao.probabilidades
    primeira, segunda = sorted(
        get_args(Intencao), key=lambda intencao: probabilidades.get(intencao, 0.0), reverse=True
    )[:2]
    return (
        "Não entendi bem o que você precisa. "
        f"Você quer {_por_extenso([DESCRICOES_INTENCAO[primeira], DESCRICOES_INTENCAO[segunda]])}? "
        "Pode reformular a pergunta?"
    )


def _esclarecimento_de_sku(candidatos: Sequence[str]) -> str:
    if not candidatos:
        return ESCLARECIMENTO_DE_SKU
    return f"{ESCLARECIMENTO_DE_SKU} Você quer dizer {_por_extenso(candidatos)}?"


def _confirmacao(intencao: Intencao) -> str:
    return f"Entendi que você quer {DESCRICOES_INTENCAO[intencao]}. Se não for isso, reformule a pergunta."


def _por_extenso(nomes: Sequence[str]) -> str:
    if len(nomes) == 1:
        return nomes[0]
    return f"{', '.join(nomes[:-1])} ou {nomes[-1]}"
