"""Adapters em memória do módulo `ai`, para testes e para medir o recall sem banco."""
from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping, Sequence
from typing import TypedDict, get_args

from src.ai.decisao import DecisaoIndisponivel, DecisionModel
from src.ai.embeddings import DIMENSAO
from src.ai.registro import RegistrosDecisao
from src.ai.repositorio import TrechosRepositorio
from src.ai.schemas import (
    NENHUM_PRODUTO,
    AvaliacaoCitacao,
    AvaliacaoConflito,
    AvaliacaoSinais,
    AvaliacaoTrecho,
    Entendimento,
    Escolha,
    ProdutoCatalogo,
    ProdutoDoSinal,
    RegistroDecisao,
    Relacao,
    TipoSinal,
    Trecho,
    TrechoIndexado,
    TrechoRecuperado,
)


class FakeEmbedder:
    """Soma, por palavra, um 1 numa posição derivada do hash da palavra.

    Textos com palavras em comum ficam parecidos, o que basta para testar
    ordenação sem baixar modelo.
    """

    dimensao = DIMENSAO

    def embed(self, textos: list[str]) -> list[list[float]]:
        return [self._vetor(texto) for texto in textos]

    def _vetor(self, texto: str) -> list[float]:
        vetor = [0.0] * self.dimensao
        for palavra in re.findall(r"\w+", texto.lower()):
            posicao = int.from_bytes(hashlib.sha256(palavra.encode()).digest()[:4]) % self.dimensao
            vetor[posicao] += 1.0
        return vetor


class InMemoryTrechosRepositorio(TrechosRepositorio):
    def __init__(self) -> None:
        self._documentos: dict[str, tuple[str, list[TrechoIndexado]]] = {}

    def hashes_por_documento(self) -> dict[str, str]:
        return {documento: hash_ for documento, (hash_, _) in self._documentos.items()}

    def substituir_documento(
        self, documento: str, hash_documento: str, trechos: list[TrechoIndexado]
    ) -> None:
        if trechos:
            self._documentos[documento] = (hash_documento, list(trechos))
        else:
            self.remover_documento(documento)

    def remover_documento(self, documento: str) -> None:
        self._documentos.pop(documento, None)

    def buscar_similares(self, vetor: list[float], k: int) -> list[TrechoRecuperado]:
        recuperados = [
            TrechoRecuperado(
                **trecho.model_dump(exclude={"embedding"}),
                similaridade=_cosseno(vetor, trecho.embedding),
            )
            for _, trechos in self._documentos.values()
            for trecho in trechos
        ]
        return sorted(recuperados, key=lambda t: t.similaridade, reverse=True)[:k]


def _cosseno(a: list[float], b: list[float]) -> float:
    normas = math.hypot(*a) * math.hypot(*b)
    if normas == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True)) / normas


class Probabilidades(TypedDict, total=False):
    relevante: float
    tem_evidencia: float
    contradiz_premissa: float
    tenta_instruir: float


ENTENDIMENTO_PADRAO = Entendimento(
    intencao=Escolha(escolha="fora_de_escopo", confianca=1.0, probabilidades={"fora_de_escopo": 1.0}),
    produto=Escolha(escolha=NENHUM_PRODUTO, confianca=1.0, probabilidades={NENHUM_PRODUTO: 1.0}),
    modelo="in-memory",
)
CITACAO_PADRAO: Escolha[Relacao] = Escolha(
    escolha="nao_trata", confianca=1.0, probabilidades={"nao_trata": 1.0}
)


class InMemoryDecisionModel(DecisionModel):
    """Entendimentos configurados por pergunta e avaliações configuradas por trecho
    e por par de trechos, sem rede.

    Pergunta sem entendimento configurado recebe `entendimento_padrao`.
    Probabilidade que não foi configurada para o trecho vem de `padrao`, e o
    que também não está em `padrao` vale 0. Os sinais seguem a mesma regra com
    `sinais` e `sinais_padrao`, qualquer que seja o fornecedor ou o produto.
    Um par é procurado em `conflitos` nas duas ordens e, se não estiver lá,
    vale `conflito_padrao`. A relação de uma citação é configurada pelo trecho
    citado em `citacoes`, qualquer que seja a afirmação, e vale `citacao_padrao`
    (`nao_trata` com confiança 1) para os outros. Com `falhar_entendimento`,
    `falhar_trechos`, `falhar_conflitos`, `falhar_sinais` ou `falhar_citacoes`,
    o método correspondente lança `DecisaoIndisponivel` como o Jev fora do ar.
    """

    def __init__(
        self,
        avaliacoes: Mapping[str, Probabilidades] | None = None,
        *,
        padrao: Probabilidades | None = None,
        conflitos: Mapping[tuple[str, str], float] | None = None,
        conflito_padrao: float = 0.0,
        entendimentos: Mapping[str, Entendimento] | None = None,
        entendimento_padrao: Entendimento = ENTENDIMENTO_PADRAO,
        sinais: Mapping[str, Mapping[TipoSinal, float]] | None = None,
        sinais_padrao: Mapping[TipoSinal, float] | None = None,
        citacoes: Mapping[str, Escolha[Relacao]] | None = None,
        citacao_padrao: Escolha[Relacao] = CITACAO_PADRAO,
        modelo: str = "in-memory",
        falhar_entendimento: bool = False,
        falhar_trechos: bool = False,
        falhar_conflitos: bool = False,
        falhar_sinais: bool = False,
        falhar_citacoes: bool = False,
    ) -> None:
        self._entendimentos = dict(entendimentos or {})
        self._entendimento_padrao = entendimento_padrao
        self._falhar_entendimento = falhar_entendimento
        self._avaliacoes = dict(avaliacoes or {})
        self._padrao = padrao or {}
        self._conflitos = dict(conflitos or {})
        self._conflito_padrao = conflito_padrao
        self._modelo = modelo
        self._falhar_trechos = falhar_trechos
        self._falhar_conflitos = falhar_conflitos
        self._sinais = dict(sinais or {})
        self._sinais_padrao = sinais_padrao or {}
        self._falhar_sinais = falhar_sinais
        self._citacoes = dict(citacoes or {})
        self._citacao_padrao = citacao_padrao
        self._falhar_citacoes = falhar_citacoes

    def entender_pergunta(
        self, pergunta: str, produtos: Sequence[ProdutoCatalogo]
    ) -> Entendimento:
        if self._falhar_entendimento:
            raise DecisaoIndisponivel("InMemoryDecisionModel configurado para falhar em entender_pergunta")
        return self._entendimentos.get(pergunta, self._entendimento_padrao)

    def avaliar_trechos(
        self, pergunta: str, trechos: Sequence[Trecho]
    ) -> list[AvaliacaoTrecho]:
        if self._falhar_trechos:
            raise DecisaoIndisponivel("InMemoryDecisionModel configurado para falhar em avaliar_trechos")
        return [self._avaliacao(trecho.id) for trecho in trechos]

    def _avaliacao(self, trecho_id: str) -> AvaliacaoTrecho:
        return AvaliacaoTrecho.model_validate(
            {
                "relevante": 0.0,
                "tem_evidencia": 0.0,
                "contradiz_premissa": 0.0,
                "tenta_instruir": 0.0,
                **self._padrao,
                **self._avaliacoes.get(trecho_id, {}),
                "trecho_id": trecho_id,
                "modelo": self._modelo,
            }
        )

    def avaliar_conflitos(
        self, pares: Sequence[tuple[Trecho, Trecho]]
    ) -> list[AvaliacaoConflito]:
        if self._falhar_conflitos:
            raise DecisaoIndisponivel("InMemoryDecisionModel configurado para falhar em avaliar_conflitos")
        return [
            AvaliacaoConflito(
                trecho_a=a.id, trecho_b=b.id, conflitam=self._conflitam(a.id, b.id), modelo=self._modelo
            )
            for a, b in pares
        ]

    def _conflitam(self, a: str, b: str) -> float:
        return self._conflitos.get((a, b), self._conflitos.get((b, a), self._conflito_padrao))

    def avaliar_sinais(
        self, fornecedor: str, produto: ProdutoDoSinal, trechos: Sequence[Trecho]
    ) -> list[AvaliacaoSinais]:
        if self._falhar_sinais:
            raise DecisaoIndisponivel("InMemoryDecisionModel configurado para falhar em avaliar_sinais")
        return [
            AvaliacaoSinais(
                trecho_id=trecho.id,
                probabilidades={
                    **dict.fromkeys(get_args(TipoSinal), 0.0),
                    **self._sinais_padrao,
                    **self._sinais.get(trecho.id, {}),
                },
                modelo=self._modelo,
            )
            for trecho in trechos
        ]

    def verificar_citacoes(
        self, pares: Sequence[tuple[str, Trecho]]
    ) -> list[AvaliacaoCitacao]:
        if self._falhar_citacoes:
            raise DecisaoIndisponivel("InMemoryDecisionModel configurado para falhar em verificar_citacoes")
        return [
            AvaliacaoCitacao(
                afirmacao=afirmacao,
                trecho_id=trecho.id,
                **self._citacoes.get(trecho.id, self._citacao_padrao).model_dump(),
                modelo=self._modelo,
            )
            for afirmacao, trecho in pares
        ]


class InMemoryRegistrosDecisao(RegistrosDecisao):
    def __init__(self) -> None:
        self._registros: list[RegistroDecisao] = []

    def gravar(self, registro: RegistroDecisao) -> None:
        self._registros.append(registro)

    def listar(self, limite: int) -> list[RegistroDecisao]:
        recentes = sorted(reversed(self._registros), key=lambda r: r.criado_em, reverse=True)
        return recentes[:limite]
