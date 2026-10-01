"""Verificação das citações de um texto redigido (ADR-0002): o código extrai cada
citação `[id]` com a frase que a contém, o Jev diz como o trecho citado se relaciona
com a frase e o código decide o veredito e marca no texto o que não foi confirmado.

A extração tolera o que o redator já escreveu de fato: colchetes lenticulares
(`【id】`), espaços e crases dentro do colchete e hífen não separável (U+2011) no id.
Colchete sem id de trecho (`[SKU/...]`, `[Política de compra ativa (v1)]`) não é
citação de trecho e fica como está.
"""
from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from src.ai.decisao import DecisaoIndisponivel, DecisionModel
from src.ai.schemas import (
    AvaliacaoCitacao,
    Citacao,
    CitacoesConferidas,
    Trecho,
    Veredito,
    VerificacaoCitacao,
)

# Recalibrado pela regra de calibração do M8 com erro crítico (`scripts/avaliar_citacoes.py`
# sobre as respostas do jev-1.13.0 gravadas no M6): acima dos trechos de outro fornecedor
# lidos como `contradiz` (`.scratch/refinamentos/issues/04-regra-de-calibracao.md`).
LIMIAR_CITACAO = 0.80

_VEREDITOS: dict[str, Veredito] = {
    "sustenta": "confirmada",
    "contradiz": "contradita",
    "nao_trata": "sem_suporte",
}
_MARCAS: dict[Veredito, str] = {
    "sem_suporte": "não confirmada",
    "incerta": "não confirmada",
    "contradita": "o trecho diz o contrário",
    "inventada": "trecho inexistente",
}

_HIFENS = "\u2010\u2011\u2012\u2013\u2212"
_HIFEN_NO_ID = str.maketrans(dict.fromkeys(_HIFENS, "-"))
_HIFEN_E_ESPACO_NA_FRASE = str.maketrans({"\u2010": "-", "\u2011": "-", "\u00a0": " ", "\u202f": " "})
_COLCHETE = re.compile(r"\[([^\[\]\n]+)\]|【([^【】\n]+)】")
_ID_DE_TRECHO = re.compile(rf"[\w./{_HIFENS}-]+\.md#[\w/~{_HIFENS}-]+")
_SEPARADOR_DE_IDS = re.compile(r"[;,]")
_FIM_DE_FRASE = re.compile(r"[.!?]+")
_MARCADOR_DE_LINHA = re.compile(r"^\s*(?:#+|>|[-*+]|\d+[.)])\s+")
_SO_PONTUACAO = re.compile(r"[\s.,;:!?()]*")


@dataclass(frozen=True)
class _Colchete:
    inicio: int
    fim: int
    ids: tuple[str, ...]
    afirmacao: str


def extrair_citacoes(texto: str) -> list[Citacao]:
    """Uma citação por id de trecho e frase, na ordem do texto. A frase termina em `.`,
    `!` ou `?` seguidos de espaço, ou na quebra de linha; citação logo depois do fim
    da frase, ou sozinha na linha, fica com a frase anterior."""
    citacoes: list[Citacao] = []
    for colchete in _colchetes(texto):
        for trecho_id in colchete.ids:
            citacao = Citacao(trecho_id=trecho_id, afirmacao=colchete.afirmacao)
            if citacao not in citacoes:
                citacoes.append(citacao)
    return citacoes


def marcar_citacoes(texto: str, verificacoes: Sequence[VerificacaoCitacao]) -> str:
    """Reescreve os colchetes com alguma citação não confirmada, mantendo os ids
    (`[<id> - não confirmada]`). Citação confirmada ou sem verificação fica como está."""
    vereditos = {(v.trecho_id, v.afirmacao): v.veredito for v in verificacoes}
    marcado = texto
    for colchete in reversed(_colchetes(texto)):
        marcas = [
            _MARCAS.get(vereditos.get((trecho_id, colchete.afirmacao), "confirmada")) for trecho_id in colchete.ids
        ]
        if not any(marcas):
            continue
        ids = "; ".join(
            trecho_id if marca is None else f"{trecho_id} - {marca}"
            for trecho_id, marca in zip(colchete.ids, marcas, strict=True)
        )
        marcado = f"{marcado[: colchete.inicio]}[{ids}]{marcado[colchete.fim :]}"
    return marcado


def veredito(avaliacao: AvaliacaoCitacao, limiar: float = LIMIAR_CITACAO) -> Veredito:
    if avaliacao.confianca < limiar:
        return "incerta"
    return _VEREDITOS[avaliacao.escolha]


def decidir_vereditos(
    citacoes: Sequence[Citacao], ids_no_contexto: Collection[str], avaliacoes: Sequence[AvaliacaoCitacao]
) -> list[VerificacaoCitacao]:
    """Id fora do contexto é `inventada`; citação do contexto sem avaliação (o modelo de
    decisão não foi consultado ou caiu) é `incerta`."""
    por_par = {(a.trecho_id, a.afirmacao): a for a in avaliacoes}
    verificacoes = []
    for citacao in citacoes:
        avaliacao = por_par.get((citacao.trecho_id, citacao.afirmacao))
        resultado: Veredito
        if citacao.trecho_id not in ids_no_contexto:
            resultado, confianca = "inventada", None
        elif avaliacao is None:
            resultado, confianca = "incerta", None
        else:
            resultado, confianca = veredito(avaliacao), avaliacao.confianca
        verificacoes.append(
            VerificacaoCitacao(
                trecho_id=citacao.trecho_id, afirmacao=citacao.afirmacao, veredito=resultado, confianca=confianca
            )
        )
    return verificacoes


def conferir_citacoes(texto: str, trechos: Sequence[Trecho], decisao: DecisionModel) -> CitacoesConferidas:
    """Verifica cada citação do `texto` contra os `trechos` que o redator podia citar e
    marca no texto as não confirmadas. Só as citações de trechos do contexto com
    afirmação vão ao modelo de decisão, uma vez por par. Com ele fora do ar, essas
    ficam `incerta` e as inventadas continuam inventadas."""
    citacoes = extrair_citacoes(texto)
    por_id = {trecho.id: trecho for trecho in trechos}
    pares = [(c.afirmacao, por_id[c.trecho_id]) for c in citacoes if c.trecho_id in por_id and c.afirmacao]
    indisponivel = False
    try:
        avaliacoes = decisao.verificar_citacoes(pares) if pares else []
    except DecisaoIndisponivel:
        avaliacoes, indisponivel = [], True
    verificacoes = decidir_vereditos(citacoes, por_id.keys(), avaliacoes)
    return CitacoesConferidas(
        texto=marcar_citacoes(texto, verificacoes), verificacoes=verificacoes, decisao_indisponivel=indisponivel
    )


def _colchetes(texto: str) -> list[_Colchete]:
    colchetes: list[_Colchete] = []
    ultima_afirmacao = ""
    for inicio_linha, linha in _linhas(texto):
        todos = list(_COLCHETE.finditer(linha))
        citacoes = [(m, ids) for m in todos if (ids := _ids(m))]
        inicio = 0
        for fim in [*_fins_de_frase(linha, todos, [m for m, _ in citacoes]), len(linha)]:
            da_frase = [(m, ids) for m, ids in citacoes if inicio <= m.start() < fim]
            afirmacao = _afirmacao(linha[inicio:fim], [(m.start() - inicio, m.end() - inicio) for m, _ in da_frase])
            ultima_afirmacao = afirmacao or ultima_afirmacao
            colchetes.extend(
                _Colchete(inicio_linha + m.start(), inicio_linha + m.end(), ids, ultima_afirmacao)
                for m, ids in da_frase
            )
            inicio = fim
    return colchetes


def _linhas(texto: str) -> list[tuple[int, str]]:
    linhas, inicio = [], 0
    for linha in texto.split("\n"):
        linhas.append((inicio, linha))
        inicio += len(linha) + 1
    return linhas


def _ids(colchete: re.Match[str]) -> tuple[str, ...]:
    conteudo = colchete.group(1) or colchete.group(2)
    partes = (parte.strip().strip("`").strip() for parte in _SEPARADOR_DE_IDS.split(conteudo))
    return tuple(parte.translate(_HIFEN_NO_ID) for parte in partes if _ID_DE_TRECHO.fullmatch(parte))


def _fins_de_frase(linha: str, colchetes: list[re.Match[str]], citacoes: list[re.Match[str]]) -> list[int]:
    """Um fim de frase é pontuação final fora de colchete, seguida de espaço ou do fim da
    linha. Citações logo depois da pontuação entram na frase que termina ali."""
    inicios_de_citacao = {m.start(): m.end() for m in citacoes}
    fins = []
    for pontuacao in _FIM_DE_FRASE.finditer(linha):
        if any(c.start() <= pontuacao.start() < c.end() for c in colchetes):
            continue
        fim = pontuacao.end()
        while (proximo := len(linha) - len(linha[fim:].lstrip())) in inicios_de_citacao:
            fim = inicios_de_citacao[proximo]
        if fim < len(linha) and linha[fim].isspace():
            fins.append(fim)
    return fins


def _afirmacao(frase: str, citacoes: list[tuple[int, int]]) -> str:
    for inicio, fim in reversed(citacoes):
        frase = frase[:inicio] + frase[fim:]
    if _SO_PONTUACAO.fullmatch(frase):
        return ""
    frase = _MARCADOR_DE_LINHA.sub("", frase.translate(_HIFEN_E_ESPACO_NA_FRASE))
    frase = re.sub(r"[*`]", "", frase)
    frase = re.sub(r"\(\s*\)", "", frase)
    frase = re.sub(r"\s+", " ", frase)
    return re.sub(r"\s+([.,;:!?)])", r"\1", frase).strip()
