"""Avaliação dos sinais do corpus contra o Jev real (M6, ticket 01).

Roda `JevDecisionModel.avaliar_sinais` nos casos de `evals/sinais.json`, um
request por caso com o trecho do corpus, grava as respostas cruas e imprime, por
tipo de sinal, a probabilidade de cada caso e a varredura do limiar. Um trecho
vira sinal quando a probabilidade passa do limiar. Pela regra da spec, o limiar
de cada tipo é o de mais acertos na varredura; no empate, o mais alto.

    uv run python -m scripts.avaliar_sinais          # chama o Jev (precisa de JEV_KEY)
    uv run python -m scripts.avaliar_sinais --de-arquivo evals/resultados/sinais-AAAA-MM-DD.json
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

from src.ai.corpus import ler_corpus
from src.ai.decisao import DecisionModel
from src.ai.jev import PERGUNTAS_SINAIS, JevDecisionModel, criar_cliente
from src.ai.schemas import AvaliacaoSinais, ProdutoDoSinal, TipoSinal, Trecho
from src.db.config import get_settings

RAIZ = Path(__file__).resolve().parents[1]
CASOS = RAIZ / "evals" / "sinais.json"
RESULTADOS = RAIZ / "evals" / "resultados"

LIMIARES = tuple(round(0.30 + 0.05 * i, 2) for i in range(13))
TIPOS: tuple[TipoSinal, ...] = get_args(TipoSinal)


@dataclass(frozen=True)
class PontoVarredura:
    limiar: float
    acertos: int
    falsos_positivos: int
    falsos_negativos: int


def rodar(decisao: DecisionModel, casos: list[dict], trechos: Mapping[str, Trecho]) -> list[dict]:
    respostas = []
    for caso in casos:
        inicio = perf_counter()
        [avaliacao] = decisao.avaliar_sinais(
            caso["fornecedor"], ProdutoDoSinal.model_validate(caso["produto"]), [trechos[caso["trecho_id"]]]
        )
        respostas.append(
            {
                "caso": caso["id"],
                "latencia_s": round(perf_counter() - inicio, 3),
                "avaliacao": avaliacao.model_dump(mode="json"),
            }
        )
    return respostas


def avaliacoes(resultado: dict) -> dict[str, AvaliacaoSinais]:
    return {r["caso"]: AvaliacaoSinais.model_validate(r["avaliacao"]) for r in resultado["respostas"]}


def varrer_limiar(tipo: TipoSinal, casos: list[dict], por_caso: dict[str, AvaliacaoSinais]) -> list[PontoVarredura]:
    pontos = []
    for limiar in LIMIARES:
        falsos_positivos = falsos_negativos = 0
        for caso in casos:
            sinal = getattr(por_caso[caso["id"]], tipo) > limiar
            esperado = caso["esperado"][tipo]
            falsos_positivos += sinal and not esperado
            falsos_negativos += esperado and not sinal
        acertos = len(casos) - falsos_positivos - falsos_negativos
        pontos.append(PontoVarredura(limiar, acertos, falsos_positivos, falsos_negativos))
    return pontos


def escolher_limiar(varredura: list[PontoVarredura]) -> float:
    return max(varredura, key=lambda p: (p.acertos, p.limiar)).limiar


def relatorio(resultado: dict, casos: list[dict]) -> str:
    por_caso = avaliacoes(resultado)
    linhas = [f"Modelo: {', '.join(sorted({a.modelo for a in por_caso.values()}))}"]
    latencias = sorted(r["latencia_s"] for r in resultado["respostas"])
    linhas.append(f"Latência: mediana {latencias[len(latencias) // 2]:.3f} s, máxima {latencias[-1]:.3f} s")

    escolhidos: dict[TipoSinal, float] = {}
    for tipo in TIPOS:
        positivos = sum(caso["esperado"][tipo] for caso in casos)
        linhas.append(f"\n## {tipo} ({positivos} positivos em {len(casos)} casos)")
        for caso in sorted(casos, key=lambda c: getattr(por_caso[c["id"]], tipo), reverse=True):
            rotulo = "sim" if caso["esperado"][tipo] else "não"
            linhas.append(
                f"  {getattr(por_caso[caso['id']], tipo):.2f}  esperado {rotulo}  {caso['id']} "
                f"{caso['fornecedor']} / {caso['produto']['nome']} x {caso['trecho_id']}"
            )
        varredura = varrer_limiar(tipo, casos, por_caso)
        linhas.append("  limiar  acertos  falsos+  falsos-")
        for ponto in varredura:
            linhas.append(
                f"  {ponto.limiar:.2f}    {ponto.acertos:>7}  {ponto.falsos_positivos:>7}  {ponto.falsos_negativos:>7}"
            )
        escolhidos[tipo] = escolher_limiar(varredura)
        linhas.append(f"  {tipo}: {escolhidos[tipo]:.2f} (mais acertos; no empate, o mais alto)")

    argumentos = ", ".join(f"{tipo}={escolhidos[tipo]:.2f}" for tipo in TIPOS)
    linhas.append(f"\nLIMIARES_SINAIS = LimiaresSinais({argumentos})")
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
        arquivo = RESULTADOS / f"sinais-{date.today().isoformat()}.json"
        if arquivo.exists():
            raise SystemExit(f"{arquivo} já existe; use --de-arquivo para recalcular")
        trechos = {t.id: t for t in ler_corpus(settings.corpus_dir)}
        with criar_cliente(settings.jev_key, settings.jev_model) as cliente:
            respostas = rodar(JevDecisionModel(cliente), casos, trechos)
        resultado = {
            "executado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "modelo_pedido": settings.jev_model,
            "perguntas": {nome: pergunta.model_dump() for nome, pergunta in PERGUNTAS_SINAIS.items()},
            "respostas": respostas,
        }
        RESULTADOS.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Respostas cruas em {arquivo.relative_to(RAIZ)}", file=sys.stderr)

    print(relatorio(resultado, casos))


if __name__ == "__main__":
    main()
