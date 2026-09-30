"""Rodada dos casos de `evals/casos.json` pelo chat inteiro (M5, ticket 05).

Monta o `Copilot` como o `POST /chat` (Jev real, redator configurado no `.env`,
ERP, política e corpus do Postgres) e responde as perguntas dos casos. Cada
resposta grava um registro de decisão em `copilot.registros_decisao`, como no
chat. Imprime por caso a intenção esperada e a escolhida, a confiança, a faixa,
a ação, os SKUs, o redator e a duração, e no fim o total por faixa e por ação.

    uv run python -m scripts.rodar_casos_chat               # precisa de JEV_KEY, do seed e do corpus ingerido
    uv run python -m scripts.rodar_casos_chat --respostas   # imprime também o texto de cada resposta
    uv run python -m scripts.rodar_casos_chat --pausa 30    # espera entre os casos (limite de tokens por minuto da Groq)
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from time import perf_counter, sleep

from src.ai.busca import BuscaContexto
from src.ai.chat import Copilot, RespostaCopilot
from src.ai.dependencies import (
    get_decision_model,
    get_embedder,
    get_redator,
    get_registros_decisao,
    get_trechos_repositorio,
)
from src.catalog.service import Catalog
from src.db.config import get_settings
from src.erp_adapter.dependencies import get_erp_adapter
from src.ficha_sku.service import FichaSKU
from src.inventory.service import Inventory
from src.politica_compra.dependencies import get_politica_compra_repositorio
from src.purchasing.service import Purchasing
from src.sales.service import Sales

RAIZ = Path(__file__).resolve().parents[1]
CASOS = RAIZ / "evals" / "casos.json"


def montar_copilot() -> Copilot:
    decisao = get_decision_model()
    erp = get_erp_adapter()
    catalog = Catalog(erp)
    sales = Sales(erp)
    inventory = Inventory(erp, sales)
    ficha_sku = FichaSKU(catalog, inventory, sales)
    politicas = get_politica_compra_repositorio()
    return Copilot(
        decisao,
        catalog,
        ficha_sku,
        Purchasing(ficha_sku, inventory, sales, politicas),
        politicas,
        BuscaContexto(get_embedder(), get_trechos_repositorio(), decisao),
        get_redator(),
        get_registros_decisao(),
    )


def linha(caso: dict, resposta: RespostaCopilot, segundos: float) -> str:
    intencao = resposta.entendimento.intencao
    marca = "ok  " if intencao.escolha == caso["intencao"] else "ERRO"
    skus = ", ".join(resposta.identificacao.skus) if resposta.identificacao else "-"
    if resposta.identificacao and resposta.identificacao.candidatos:
        skus += f" (candidatos: {', '.join(resposta.identificacao.candidatos)})"
    return (
        f"{marca} {caso['id']} esperada {caso['intencao']}, escolhida {intencao.escolha} "
        f"({intencao.confianca:.2f}), faixa {resposta.faixa}, {resposta.acao}, "
        f"redator {resposta.redator or '-'}, {segundos:.1f} s\n"
        f"     SKUs: {skus}\n"
        f"     {caso['pergunta']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--respostas", action="store_true", help="imprime também o texto de cada resposta")
    parser.add_argument("--pausa", type=float, default=0.0, help="segundos de espera entre um caso e o seguinte")
    args = parser.parse_args()

    if not get_settings().jev_key:
        raise SystemExit("JEV_KEY vazio no .env")
    casos = json.loads(CASOS.read_text(encoding="utf-8"))
    copilot = montar_copilot()

    faixas: Counter[str] = Counter()
    acoes: Counter[str] = Counter()
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
        acertos += resposta.entendimento.intencao.escolha == caso["intencao"]

    print(f"Intenção: {acertos}/{len(casos)}")
    print("Faixas: " + ", ".join(f"{f} {faixas[f]}" for f in ("alta", "media", "baixa")))
    print("Ações: " + ", ".join(f"{a} {n}" for a, n in acoes.most_common()))


if __name__ == "__main__":
    main()
