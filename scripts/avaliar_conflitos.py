"""Avaliação do conflito entre trechos contra o Jev real (M8, ticket 05).

Duas etapas, nesta ordem:

1. `--juntar`: roda a busca (com conflitos) das perguntas de `evals/casos.json` que vão
   ao corpus (`sugestao_compra` e `politica_ou_fornecedor`), grava todo par que a busca
   mandou ao Jev, com a probabilidade, em `evals/resultados/buscas-conflito-<data>-<rotulo>.json`
   e imprime os pares que passaram do limiar atual e ainda não estão em
   `evals/pares_conflito.json`, com o texto dos dois trechos e sem a probabilidade, para
   rotular às cegas.
2. Avaliação: roda `JevDecisionModel.avaliar_conflitos` nos pares rotulados, um request
   por par, grava as respostas cruas em `evals/resultados/conflitos-<data>-<rotulo>.json`
   e imprime a probabilidade de cada par e a varredura do limiar. Um par vira conflito
   quando a probabilidade passa do limiar. O `LIMIARES.conflito` sai da regra de
   calibração do M8 (`scripts/calibracao.py`), sem erro crítico: positivos são os pares
   que conflitam e negativos os outros. Separável, o ponto médio entre o maior negativo
   e o menor positivo; senão, o meio da faixa de mais acertos; com menos de 3 de cada,
   o limiar atual fica. Com `--buscas`, o relatório conta, por pergunta, os pares
   daquelas buscas que passam do limiar atual e do calibrado.

    uv run python -m scripts.avaliar_conflitos --juntar --rotulo antes   # chama o Jev (JEV_KEY e o corpus no banco)
    uv run python -m scripts.avaliar_conflitos --rotulo antes
    uv run python -m scripts.avaliar_conflitos --de-arquivo evals/resultados/conflitos-AAAA-MM-DD-antes.json \\
        --buscas evals/resultados/buscas-conflito-AAAA-MM-DD-antes.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from time import perf_counter

from scripts.calibracao import Calibracao, calibrar, descrever, formatar_limiar
from src.ai.busca import LIMIARES as LIMIARES_BUSCA, BuscaContexto
from src.ai.corpus import ler_corpus
from src.ai.decisao import DecisionModel
from src.ai.embeddings import Embedder, FastEmbedEmbedder
from src.ai.jev import PERGUNTAS_CONFLITO, JevDecisionModel, criar_cliente
from src.ai.postgres import PostgresTrechosRepositorio
from src.ai.repositorio import TrechosRepositorio
from src.ai.schemas import AvaliacaoConflito, AvaliacaoTrecho, Trecho
from src.db.config import get_settings
from src.db.engine import get_engine

RAIZ = Path(__file__).resolve().parents[1]
PARES = RAIZ / "evals" / "pares_conflito.json"
CASOS = RAIZ / "evals" / "casos.json"
RESULTADOS = RAIZ / "evals" / "resultados"

LIMIARES = tuple(round(0.05 + 0.05 * i, 2) for i in range(18))
INTENCOES_COM_BUSCA = ("sugestao_compra", "politica_ou_fornecedor")

Par = tuple[str, str]


@dataclass(frozen=True)
class PontoVarredura:
    limiar: float
    acertos: int
    falsos_positivos: int
    falsos_negativos: int


class GravaConflitos(DecisionModel):
    """Repassa ao modelo de decisão o que a busca usa e guarda toda avaliação de conflito,
    inclusive as que ficam abaixo do limiar."""

    def __init__(self, decisao: DecisionModel) -> None:
        self._decisao = decisao
        self.conflitos: list[AvaliacaoConflito] = []

    def avaliar_trechos(self, pergunta: str, trechos: Sequence[Trecho]) -> list[AvaliacaoTrecho]:
        return self._decisao.avaliar_trechos(pergunta, trechos)

    def avaliar_conflitos(self, pares: Sequence[tuple[Trecho, Trecho]]) -> list[AvaliacaoConflito]:
        avaliacoes = self._decisao.avaliar_conflitos(pares)
        self.conflitos.extend(avaliacoes)
        return avaliacoes


def perguntas_com_busca(casos: list[dict]) -> list[dict]:
    return [caso for caso in casos if caso["intencao"] in INTENCOES_COM_BUSCA]


def juntar(
    embedder: Embedder, repositorio: TrechosRepositorio, decisao: DecisionModel, casos: list[dict]
) -> list[dict]:
    """Toda avaliação de conflito de cada busca, na ordem em que a busca mandou os pares."""
    buscas = []
    for caso in perguntas_com_busca(casos):
        gravador = GravaConflitos(decisao)
        BuscaContexto(embedder, repositorio, gravador).buscar(caso["pergunta"])
        buscas.append(
            {
                "caso": caso["id"],
                "pergunta": caso["pergunta"],
                "pares": [a.model_dump(mode="json") for a in gravador.conflitos],
            }
        )
    return buscas


def pares_acima(buscas: list[dict], limiar: float) -> list[Par]:
    """Os pares das buscas que passam do limiar, uma vez cada (em qualquer ordem), na ordem em que aparecem."""
    vistos: set[frozenset[str]] = set()
    pares = []
    for busca in buscas:
        for par in busca["pares"]:
            chave = frozenset((par["trecho_a"], par["trecho_b"]))
            if par["conflitam"] > limiar and chave not in vistos:
                vistos.add(chave)
                pares.append((par["trecho_a"], par["trecho_b"]))
    return pares


def pares_para_rotular(buscas: list[dict], rotulados: list[dict], limiar: float) -> list[Par]:
    ja_rotulados = {frozenset((par["trecho_a"], par["trecho_b"])) for par in rotulados}
    return [par for par in pares_acima(buscas, limiar) if frozenset(par) not in ja_rotulados]


def conflitos_por_pergunta(buscas: list[dict], limiar: float) -> dict[str, int]:
    return {busca["caso"]: sum(par["conflitam"] > limiar for par in busca["pares"]) for busca in buscas}


def texto_para_rotular(pares: list[Par], trechos: Mapping[str, Trecho]) -> str:
    blocos = []
    for numero, par in enumerate(pares, start=1):
        linhas = [f"## Par {numero}"]
        for id in par:
            trecho = trechos[id]
            linhas += [f"### {id} ({trecho.tipo}, {trecho.data.isoformat()})", trecho.texto]
        blocos.append("\n".join(linhas))
    return "\n\n".join(blocos)


def nome_do_resultado(dia: date, rotulo: str | None, prefixo: str = "conflitos") -> str:
    return f"{prefixo}-{dia.isoformat()}{f'-{rotulo}' if rotulo else ''}.json"


def rodar(decisao: DecisionModel, pares: list[dict], trechos: Mapping[str, Trecho]) -> list[dict]:
    respostas = []
    for par in pares:
        inicio = perf_counter()
        [avaliacao] = decisao.avaliar_conflitos([(trechos[par["trecho_a"]], trechos[par["trecho_b"]])])
        respostas.append(
            {"latencia_s": round(perf_counter() - inicio, 3), "avaliacao": avaliacao.model_dump(mode="json")}
        )
    return respostas


def avaliacoes(resultado: dict) -> dict[Par, AvaliacaoConflito]:
    por_par = {}
    for resposta in resultado["respostas"]:
        avaliacao = AvaliacaoConflito.model_validate(resposta["avaliacao"])
        por_par[(avaliacao.trecho_a, avaliacao.trecho_b)] = avaliacao
    return por_par


def _probabilidade(par: dict, por_par: dict[Par, AvaliacaoConflito]) -> float:
    return por_par[(par["trecho_a"], par["trecho_b"])].conflitam


def varrer_limiar(pares: list[dict], por_par: dict[Par, AvaliacaoConflito]) -> list[PontoVarredura]:
    pontos = []
    for limiar in LIMIARES:
        falsos_positivos = falsos_negativos = 0
        for par in pares:
            conflito = _probabilidade(par, por_par) > limiar
            falsos_positivos += conflito and not par["conflitam"]
            falsos_negativos += par["conflitam"] and not conflito
        pontos.append(PontoVarredura(limiar, len(pares) - falsos_positivos - falsos_negativos, falsos_positivos, falsos_negativos))
    return pontos


def calibrar_conflito(pares: list[dict], por_par: dict[Par, AvaliacaoConflito]) -> Calibracao:
    def probabilidades(conflitam: bool) -> list[float]:
        return [_probabilidade(par, por_par) for par in pares if par["conflitam"] == conflitam]

    return calibrar(probabilidades(True), probabilidades(False), atual=LIMIARES_BUSCA.conflito)


def relatorio(resultado: dict, pares: list[dict], buscas: list[dict] | None = None) -> str:
    por_par = avaliacoes(resultado)
    linhas = [f"Modelo: {', '.join(sorted({a.modelo for a in por_par.values()}))}"]
    latencias = sorted(r["latencia_s"] for r in resultado["respostas"])
    linhas.append(f"Latência: mediana {latencias[len(latencias) // 2]:.3f} s, máxima {latencias[-1]:.3f} s")

    com_conflito = sum(par["conflitam"] for par in pares)
    linhas.append(f"\n## Pares ({com_conflito} com conflito e {len(pares) - com_conflito} sem)")
    for par in sorted(pares, key=lambda p: _probabilidade(p, por_par), reverse=True):
        rotulo = "sim" if par["conflitam"] else "não"
        linhas.append(f"  {_probabilidade(par, por_par):.2f}  conflitam {rotulo}  {par['trecho_a']} x {par['trecho_b']}")

    linhas.append("\n## Varredura do limiar")
    linhas.append("  limiar  acertos  falsos+  falsos-")
    for ponto in varrer_limiar(pares, por_par):
        linhas.append(
            f"  {ponto.limiar:.2f}    {ponto.acertos:>7}  {ponto.falsos_positivos:>7}  {ponto.falsos_negativos:>7}"
        )
    calibracao = calibrar_conflito(pares, por_par)
    linhas.append(f"\nRegra de calibração: {descrever(calibracao)}")
    linhas.append(f"LIMIARES.conflito = {formatar_limiar(calibracao.limiar)}")

    if buscas is not None:
        atual, novo = (conflitos_por_pergunta(buscas, limiar) for limiar in (calibracao.atual, calibracao.limiar))
        linhas.append(
            f"\n## Conflitos por busca (limiar atual {formatar_limiar(calibracao.atual)} "
            f"e calibrado {formatar_limiar(calibracao.limiar)})"
        )
        for busca in buscas:
            caso = busca["caso"]
            linhas.append(f"  {caso}  {len(busca['pares']):>2} pares  {atual[caso]:>2} -> {novo[caso]:>2}  {busca['pergunta']}")
        linhas.append(f"  total: {sum(atual.values())} -> {sum(novo.values())}")
    return "\n".join(linhas)


def _gravar(arquivo: Path, conteudo: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Respostas cruas em {arquivo.relative_to(RAIZ)}", file=sys.stderr)


def _juntar(pares: list[dict], rotulo: str | None) -> None:
    settings = get_settings()
    if not settings.jev_key:
        raise SystemExit("JEV_KEY vazio no .env")
    arquivo = RESULTADOS / nome_do_resultado(date.today(), rotulo, prefixo="buscas-conflito")
    if arquivo.exists():
        raise SystemExit(f"{arquivo} já existe")
    casos = json.loads(CASOS.read_text(encoding="utf-8"))
    embedder = FastEmbedEmbedder(settings.embedding_model, settings.fastembed_cache_path)
    with criar_cliente(settings.jev_key, settings.jev_model) as cliente:
        buscas = juntar(embedder, PostgresTrechosRepositorio(get_engine()), JevDecisionModel(cliente), casos)
    _gravar(
        arquivo,
        {
            "executado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "modelo_pedido": settings.jev_model,
            "limiar": LIMIARES_BUSCA.conflito,
            "perguntas": {nome: pergunta.model_dump() for nome, pergunta in PERGUNTAS_CONFLITO.items()},
            "buscas": buscas,
        },
    )
    novos = pares_para_rotular(buscas, pares, LIMIARES_BUSCA.conflito)
    trechos = {t.id: t for t in ler_corpus(settings.corpus_dir)}
    print(f"{len(novos)} pares acima de {formatar_limiar(LIMIARES_BUSCA.conflito)} fora de {PARES.relative_to(RAIZ)}\n")
    print(texto_para_rotular(novos, trechos))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--juntar", action="store_true", help="roda as buscas e imprime os pares novos para rotular")
    parser.add_argument("--rotulo", help="sufixo no nome do resultado: conflitos-<data>-<rotulo>.json ou buscas-conflito-<data>-<rotulo>.json")
    parser.add_argument("--de-arquivo", type=Path, help="recalcula as métricas de um resultado gravado, sem chamar o Jev")
    parser.add_argument("--buscas", type=Path, help="buscas gravadas pelo --juntar, para contar os conflitos por pergunta")
    args = parser.parse_args()

    pares = json.loads(PARES.read_text(encoding="utf-8"))
    if args.juntar:
        _juntar(pares, args.rotulo)
        return
    if args.de_arquivo:
        resultado = json.loads(args.de_arquivo.read_text(encoding="utf-8"))
        sem_resposta = {(p["trecho_a"], p["trecho_b"]) for p in pares} - set(avaliacoes(resultado))
        if sem_resposta:
            raise SystemExit(f"pares sem resposta em {args.de_arquivo}: {', '.join(' x '.join(p) for p in sorted(sem_resposta))}")
    else:
        settings = get_settings()
        if not settings.jev_key:
            raise SystemExit("JEV_KEY vazio no .env")
        arquivo = RESULTADOS / nome_do_resultado(date.today(), args.rotulo)
        if arquivo.exists():
            raise SystemExit(f"{arquivo} já existe; use --de-arquivo para recalcular")
        trechos = {t.id: t for t in ler_corpus(settings.corpus_dir)}
        with criar_cliente(settings.jev_key, settings.jev_model) as cliente:
            respostas = rodar(JevDecisionModel(cliente), pares, trechos)
        resultado = {
            "executado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "modelo_pedido": settings.jev_model,
            "perguntas": {nome: pergunta.model_dump() for nome, pergunta in PERGUNTAS_CONFLITO.items()},
            "respostas": respostas,
        }
        _gravar(arquivo, resultado)

    buscas = json.loads(args.buscas.read_text(encoding="utf-8"))["buscas"] if args.buscas else None
    print(relatorio(resultado, pares, buscas))


if __name__ == "__main__":
    main()
