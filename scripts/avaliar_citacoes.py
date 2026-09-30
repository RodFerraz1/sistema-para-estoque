"""Avaliação da verificação de citações contra o Jev real (M6, ticket 02).

Roda `JevDecisionModel.verificar_citacoes` nos pares de `evals/citacoes.json`, um
request por par com o trecho do corpus, grava as respostas cruas e imprime o acerto
por relação e a varredura do limiar: para cada limiar, quantas citações ficariam
`incerta` (confiança abaixo dele), quantos erros sobram entre as decididas e quantas
seriam `confirmada` sem o trecho sustentar a afirmação. Pela regra da spec, o
`LIMIAR_CITACAO` é o menor limiar sem nenhuma `confirmada` errada; se nenhum zerar, 0,95.

    uv run python -m scripts.avaliar_citacoes          # chama o Jev (precisa de JEV_KEY)
    uv run python -m scripts.avaliar_citacoes --de-arquivo evals/resultados/citacoes-AAAA-MM-DD.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import get_args

from src.ai.citacoes import veredito
from src.ai.corpus import ler_corpus
from src.ai.decisao import DecisionModel
from src.ai.jev import PERGUNTAS_CITACAO, JevDecisionModel, criar_cliente
from src.ai.schemas import AvaliacaoCitacao, Relacao, Trecho
from src.db.config import get_settings

RAIZ = Path(__file__).resolve().parents[1]
CASOS = RAIZ / "evals" / "citacoes.json"
RESULTADOS = RAIZ / "evals" / "resultados"

LIMIARES = tuple(round(0.50 + 0.05 * i, 2) for i in range(10))
LIMIAR_SEM_ZERO = 0.95
RELACOES: tuple[Relacao, ...] = get_args(Relacao)


@dataclass(frozen=True)
class PontoVarredura:
    limiar: float
    incertas: int
    erros: int
    confirmadas_erradas: int


def rodar(decisao: DecisionModel, casos: list[dict], trechos: Mapping[str, Trecho]) -> list[dict]:
    respostas = []
    for caso in casos:
        inicio = perf_counter()
        [avaliacao] = decisao.verificar_citacoes([(caso["afirmacao"], trechos[caso["trecho_id"]])])
        respostas.append(
            {
                "caso": caso["id"],
                "latencia_s": round(perf_counter() - inicio, 3),
                "avaliacao": avaliacao.model_dump(mode="json"),
            }
        )
    return respostas


def avaliacoes(resultado: dict) -> dict[str, AvaliacaoCitacao]:
    return {r["caso"]: AvaliacaoCitacao.model_validate(r["avaliacao"]) for r in resultado["respostas"]}


def acertos_por_relacao(casos: list[dict], por_caso: dict[str, AvaliacaoCitacao]) -> dict[Relacao, tuple[int, int]]:
    """(acertos, total) da escolha do Jev por relação esperada, sem olhar a confiança."""
    return {
        relacao: (
            sum(por_caso[c["id"]].escolha == relacao for c in casos if c["esperado"] == relacao),
            sum(c["esperado"] == relacao for c in casos),
        )
        for relacao in RELACOES
    }


def varrer_limiar(casos: list[dict], por_caso: dict[str, AvaliacaoCitacao]) -> list[PontoVarredura]:
    pontos = []
    for limiar in LIMIARES:
        incertas = erros = confirmadas_erradas = 0
        for caso in casos:
            avaliacao = por_caso[caso["id"]]
            resultado = veredito(avaliacao, limiar)
            if resultado == "incerta":
                incertas += 1
                continue
            erros += avaliacao.escolha != caso["esperado"]
            confirmadas_erradas += resultado == "confirmada" and caso["esperado"] != "sustenta"
        pontos.append(PontoVarredura(limiar, incertas, erros, confirmadas_erradas))
    return pontos


def escolher_limiar(varredura: list[PontoVarredura]) -> float:
    sem_confirmada_errada = [p.limiar for p in varredura if p.confirmadas_erradas == 0]
    return min(sem_confirmada_errada, default=LIMIAR_SEM_ZERO)


def relatorio(resultado: dict, casos: list[dict]) -> str:
    por_caso = avaliacoes(resultado)
    linhas = [f"Modelo: {', '.join(sorted({a.modelo for a in por_caso.values()}))}"]
    latencias = sorted(r["latencia_s"] for r in resultado["respostas"])
    linhas.append(f"Latência: mediana {latencias[len(latencias) // 2]:.3f} s, máxima {latencias[-1]:.3f} s")

    acertos = acertos_por_relacao(casos, por_caso)
    for relacao in RELACOES:
        linhas.append(f"\n## esperado {relacao} ({acertos[relacao][0]}/{acertos[relacao][1]} acertos)")
        da_relacao = [c for c in casos if c["esperado"] == relacao]
        for caso in sorted(da_relacao, key=lambda c: por_caso[c["id"]].confianca, reverse=True):
            avaliacao = por_caso[caso["id"]]
            marca = "  " if avaliacao.escolha == relacao else "x "
            linhas.append(
                f"  {marca}{avaliacao.escolha:<9} {avaliacao.confianca:.2f}  {caso['id']} "
                f"{caso['afirmacao'][:70]} x {caso['trecho_id']}"
            )

    varredura = varrer_limiar(casos, por_caso)
    linhas.append(f"\n## Varredura do limiar ({len(casos)} citações)")
    linhas.append("  limiar  incertas  erros entre as decididas  confirmadas erradas")
    for ponto in varredura:
        linhas.append(
            f"  {ponto.limiar:.2f}    {ponto.incertas:>8}  {ponto.erros:>24}  {ponto.confirmadas_erradas:>19}"
        )
    escolhido = escolher_limiar(varredura)
    if all(p.confirmadas_erradas for p in varredura):
        linhas.append(f"\nNenhum limiar zera as confirmadas erradas: {escolhido:.2f}, com o risco registrado.")
    else:
        linhas.append("\nMenor limiar sem confirmada errada.")
    linhas.append(f"LIMIAR_CITACAO = {escolhido:.2f}")
    return "\n".join(linhas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--de-arquivo", type=Path, help="recalcula as métricas de um resultado gravado, sem chamar o Jev")
    args = parser.parse_args()

    casos = json.loads(CASOS.read_text(encoding="utf-8"))
    if args.de_arquivo:
        resultado = json.loads(args.de_arquivo.read_text(encoding="utf-8"))
    else:
        settings = get_settings()
        if not settings.jev_key:
            raise SystemExit("JEV_KEY vazio no .env")
        arquivo = RESULTADOS / f"citacoes-{date.today().isoformat()}.json"
        if arquivo.exists():
            raise SystemExit(f"{arquivo} já existe; use --de-arquivo para recalcular")
        trechos = {t.id: t for t in ler_corpus(settings.corpus_dir)}
        with criar_cliente(settings.jev_key, settings.jev_model) as cliente:
            respostas = rodar(JevDecisionModel(cliente), casos, trechos)
        resultado = {
            "executado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "modelo_pedido": settings.jev_model,
            "perguntas": {nome: pergunta.model_dump() for nome, pergunta in PERGUNTAS_CITACAO.items()},
            "respostas": respostas,
        }
        RESULTADOS.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Respostas cruas em {arquivo.relative_to(RAIZ)}", file=sys.stderr)

    print(relatorio(resultado, casos))


if __name__ == "__main__":
    main()
