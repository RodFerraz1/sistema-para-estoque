"""Rodada dos casos de `evals/casos.json` pelo chat inteiro (M5, ticket 05).

Monta o `Copilot` pelo mesmo `get_copilot` do `POST /chat` (Jev real, redator
configurado no `.env`, ERP, política e corpus do Postgres) e responde as
perguntas dos casos. Cada
resposta grava um registro de decisão em `copilot.registros_decisao`, como no
chat. Imprime por caso a intenção esperada e a escolhida, a confiança, a faixa,
a ação, os SKUs, os sinais do corpus, os vereditos das citações, o redator e a
duração, e no fim o total por faixa, por ação e por veredito.

    uv run python -m scripts.rodar_casos_chat               # precisa de JEV_KEY, do seed e do corpus ingerido
    uv run python -m scripts.rodar_casos_chat --respostas   # imprime também o texto de cada resposta
    uv run python -m scripts.rodar_casos_chat --pausa 30    # espera entre os casos (limite de tokens por minuto da Groq)
    uv run python -m scripts.rodar_casos_chat --sem-llm     # troca o redator pelo RedatorSemLLM
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from time import perf_counter, sleep

from scripts.dependencias import resolver
from src.ai.dependencies import get_copilot, get_redator
from src.ai.redator import RedatorSemLLM
from src.ai.schemas import RespostaCopilot
from src.db.config import get_settings

RAIZ = Path(__file__).resolve().parents[1]
CASOS = RAIZ / "evals" / "casos.json"


def linha(caso: dict, resposta: RespostaCopilot, segundos: float) -> str:
    intencao = resposta.entendimento.intencao
    marca = "ok  " if intencao.escolha == caso["intencao"] else "ERRO"
    skus = ", ".join(resposta.identificacao.skus) if resposta.identificacao else "-"
    if resposta.identificacao and resposta.identificacao.candidatos:
        skus += f" (candidatos: {', '.join(resposta.identificacao.candidatos)})"
    sinais = "; ".join(
        f"{s.sugestao.sku_code}: {', '.join(sinal.tipo for sinal in s.sinais)}" for s in resposta.sugestoes if s.sinais
    )
    vereditos = Counter(c.veredito for c in resposta.citacoes)
    return (
        f"{marca} {caso['id']} esperada {caso['intencao']}, escolhida {intencao.escolha} "
        f"({intencao.confianca:.2f}), faixa {resposta.faixa}, {resposta.acao}, "
        f"redator {resposta.redator or '-'}, {segundos:.1f} s\n"
        f"     SKUs: {skus}\n"
        f"     Sinais: {sinais or '-'}\n"
        f"     Citações: {', '.join(f'{v} {n}' for v, n in vereditos.most_common()) or '-'}\n"
        f"     {caso['pergunta']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--respostas", action="store_true", help="imprime também o texto de cada resposta")
    parser.add_argument("--pausa", type=float, default=0.0, help="segundos de espera entre um caso e o seguinte")
    parser.add_argument("--sem-llm", action="store_true", help="troca o redator pelo RedatorSemLLM")
    args = parser.parse_args()

    if not get_settings().jev_key:
        raise SystemExit("JEV_KEY vazio no .env")
    casos = json.loads(CASOS.read_text(encoding="utf-8"))
    copilot = resolver(get_copilot, {get_redator: RedatorSemLLM} if args.sem_llm else None)

    faixas: Counter[str] = Counter()
    acoes: Counter[str] = Counter()
    vereditos: Counter[str] = Counter()
    acertos = 0
    for i, caso in enumerate(casos):
        if i and args.pausa:
            sleep(args.pausa)
        inicio = perf_counter()
        resposta = copilot.responder(caso["pergunta"])
        print(linha(caso, resposta, perf_counter() - inicio))
        if args.respostas:
            print("\n".join(f"     | {t}" for t in resposta.resposta.splitlines()))
        print()
        faixas[resposta.faixa] += 1
        acoes[resposta.acao] += 1
        vereditos.update(c.veredito for c in resposta.citacoes)
        acertos += resposta.entendimento.intencao.escolha == caso["intencao"]

    print(f"Intenção: {acertos}/{len(casos)}")
    print("Faixas: " + ", ".join(f"{f} {faixas[f]}" for f in ("alta", "media", "baixa")))
    print("Ações: " + ", ".join(f"{a} {n}" for a, n in acoes.most_common()))
    print("Citações: " + (", ".join(f"{v} {n}" for v, n in vereditos.most_common()) or "nenhuma"))


if __name__ == "__main__":
    main()
