"""Avaliação do entendimento da pergunta do chat contra o Jev real (M5, ticket 01).

Roda `JevDecisionModel.entender_pergunta` nos casos de `evals/casos.json`, com os
produtos do catálogo lidos do banco (seed), grava as respostas cruas e imprime o
acerto da intenção, o acerto do produto (escolha dentro de `produtos_aceitos`) e
a varredura do limiar do produto. Pela regra da spec, `LIMIAR_PRODUTO` é o menor
limiar da varredura em que nenhum produto errado é usado; se nenhum zera os
erros, vale 0,80.

    uv run python -m scripts.avaliar_entendimento          # chama o Jev (precisa de JEV_KEY e do seed)
    uv run python -m scripts.avaliar_entendimento --de-arquivo evals/resultados/entendimento-AAAA-MM-DD.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from time import perf_counter

from src.ai.decisao import DecisionModel
from src.ai.identificacao import produtos_do_catalogo
from src.ai.jev import PERGUNTA_INTENCAO, JevDecisionModel, criar_cliente, pergunta_produto
from src.ai.schemas import NENHUM_PRODUTO, Entendimento, ProdutoCatalogo
from src.catalog.service import Catalog
from src.db.config import get_settings
from src.db.engine import get_engine
from src.erp_adapter.postgres import PostgresERPAdapter

RAIZ = Path(__file__).resolve().parents[1]
CASOS = RAIZ / "evals" / "casos.json"
RESULTADOS = RAIZ / "evals" / "resultados"

LIMIARES = tuple(round(0.30 + 0.05 * i, 2) for i in range(14))
LIMIAR_SEM_ZERO_ERROS = 0.80


@dataclass(frozen=True)
class PontoVarredura:
    limiar: float
    certos: int
    errados: int


def rodar(decisao: DecisionModel, casos: list[dict], produtos: list[ProdutoCatalogo]) -> list[dict]:
    respostas = []
    for caso in casos:
        inicio = perf_counter()
        entendimento = decisao.entender_pergunta(caso["pergunta"], produtos)
        respostas.append(
            {
                "caso": caso["id"],
                "latencia_s": round(perf_counter() - inicio, 3),
                "entendimento": entendimento.model_dump(mode="json"),
            }
        )
    return respostas


def entendimentos(resultado: dict) -> dict[str, Entendimento]:
    return {r["caso"]: Entendimento.model_validate(r["entendimento"]) for r in resultado["respostas"]}


def erros_de_intencao(casos: list[dict], por_caso: dict[str, Entendimento]) -> list[tuple[dict, Entendimento]]:
    return [(c, por_caso[c["id"]]) for c in casos if por_caso[c["id"]].intencao.escolha != c["intencao"]]


def erros_de_produto(casos: list[dict], por_caso: dict[str, Entendimento]) -> list[tuple[dict, Entendimento]]:
    return [(c, por_caso[c["id"]]) for c in casos if not _produto_certo(c, por_caso[c["id"]])]


def varrer_limiar_produto(casos: list[dict], por_caso: dict[str, Entendimento]) -> list[PontoVarredura]:
    pontos = []
    for limiar in LIMIARES:
        usados = [
            c
            for c in casos
            if por_caso[c["id"]].produto.escolha != NENHUM_PRODUTO and por_caso[c["id"]].produto.confianca >= limiar
        ]
        certos = sum(_produto_certo(c, por_caso[c["id"]]) for c in usados)
        pontos.append(PontoVarredura(limiar, certos, len(usados) - certos))
    return pontos


def escolher_limiar_produto(varredura: list[PontoVarredura]) -> float:
    return next((p.limiar for p in varredura if p.errados == 0), LIMIAR_SEM_ZERO_ERROS)


def _produto_certo(caso: dict, entendimento: Entendimento) -> bool:
    return entendimento.produto.escolha in caso["produtos_aceitos"]


def relatorio(resultado: dict, casos: list[dict]) -> str:
    por_caso = entendimentos(resultado)
    linhas = [f"Modelo: {', '.join(sorted({e.modelo for e in por_caso.values()}))}"]
    latencias = sorted(r["latencia_s"] for r in resultado["respostas"])
    linhas.append(f"Latência: mediana {latencias[len(latencias) // 2]:.3f} s, máxima {latencias[-1]:.3f} s")

    erros = erros_de_intencao(casos, por_caso)
    linhas.append(f"\nIntenção: {len(casos) - len(erros)}/{len(casos)}")
    for caso, e in erros:
        linhas.append(
            f"  {caso['id']} esperado {caso['intencao']}, veio {e.intencao.escolha} "
            f"(confiança {e.intencao.confianca:.2f}): {caso['pergunta']}"
        )

    erros = erros_de_produto(casos, por_caso)
    linhas.append(f"\nProduto: {len(casos) - len(erros)}/{len(casos)}")
    for caso in casos:
        e = por_caso[caso["id"]]
        marca = "ok  " if _produto_certo(caso, e) else "ERRO"
        linhas.append(
            f"  {marca} {caso['id']} {e.produto.escolha} (confiança {e.produto.confianca:.2f}); "
            f"aceitos: {', '.join(caso['produtos_aceitos'])}"
        )

    varredura = varrer_limiar_produto(casos, por_caso)
    linhas.append("\nVarredura do limiar do produto (produtos usados, sem contar `nenhum`):")
    linhas.append("  limiar  certos  errados")
    for ponto in varredura:
        linhas.append(f"  {ponto.limiar:.2f}    {ponto.certos:>6}  {ponto.errados:>7}")
    limiar = escolher_limiar_produto(varredura)
    if any(p.errados == 0 for p in varredura):
        linhas.append(f"\nLIMIAR_PRODUTO = {limiar:.2f} (menor limiar sem produto errado usado)")
    else:
        linhas.append(f"\nLIMIAR_PRODUTO = {limiar:.2f} (nenhum limiar zera os erros; vale o padrão da spec)")
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
        arquivo = RESULTADOS / f"entendimento-{date.today().isoformat()}.json"
        if arquivo.exists():
            raise SystemExit(f"{arquivo} já existe; use --de-arquivo para recalcular")
        produtos = produtos_do_catalogo(Catalog(PostgresERPAdapter(get_engine())).listar_skus())
        with criar_cliente(settings.jev_key, settings.jev_model) as cliente:
            respostas = rodar(JevDecisionModel(cliente), casos, produtos)
        resultado = {
            "executado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "modelo_pedido": settings.jev_model,
            "perguntas": {
                "intencao": PERGUNTA_INTENCAO.model_dump(),
                "produto": pergunta_produto(produtos).model_dump(),
            },
            "respostas": respostas,
        }
        RESULTADOS.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Respostas cruas em {arquivo.relative_to(RAIZ)}", file=sys.stderr)

    print(relatorio(resultado, casos))


if __name__ == "__main__":
    main()
