"""Recall@k da busca vetorial contra os `trechos_relevantes` de `evals/casos.json`.

Indexa o corpus em memória com o modelo de `EMBEDDING_MODEL` (não precisa de
banco) e, para cada pergunta rotulada, confere quantos trechos relevantes
aparecem entre os k mais parecidos. Critério da spec 04: recall@10 >= 0,9,
contado sobre todos os trechos rotulados (micro). A média por pergunta
(macro) sai junto como referência. Se não bater, a troca de modelo passa
pela ADR-0004.

    uv run python -m scripts.avaliar_recuperacao
"""
from __future__ import annotations

import json
from pathlib import Path

from src.ai.dependencies import get_embedder
from src.ai.in_memory import InMemoryTrechosRepositorio
from src.ai.ingestao import ingerir
from src.db.config import get_settings

RAIZ = Path(__file__).resolve().parents[1]
CASOS = RAIZ / "evals" / "casos.json"
CORTES_K = (5, 10, 15)
K_CRITERIO = 10
RECALL_MINIMO = 0.9


def main() -> None:
    if not CASOS.exists():
        raise SystemExit(
            f"{CASOS.relative_to(RAIZ)} não existe. Ele é criado pelo ticket 02 da spec 04 "
            "(casos rotulados do spike do Jev)."
        )
    casos = [c for c in json.loads(CASOS.read_text(encoding="utf-8")) if c["trechos_relevantes"]]

    embedder = get_embedder()
    repositorio = InMemoryTrechosRepositorio()
    ingerir(get_settings().corpus_dir, embedder, repositorio)
    vetores = embedder.embed([caso["pergunta"] for caso in casos])

    k_maximo = max(CORTES_K)
    total_relevantes = sum(len(caso["trechos_relevantes"]) for caso in casos)
    encontrados = dict.fromkeys(CORTES_K, 0)
    recall_por_pergunta: dict[int, list[float]] = {k: [] for k in CORTES_K}
    for caso, vetor in zip(casos, vetores, strict=True):
        ranking = [t.id for t in repositorio.buscar_similares(vetor, k=k_maximo)]
        relevantes = set(caso["trechos_relevantes"])
        for k in CORTES_K:
            achados = len(relevantes & set(ranking[:k]))
            encontrados[k] += achados
            recall_por_pergunta[k].append(achados / len(relevantes))
        perdidos = relevantes - set(ranking[:K_CRITERIO])
        if perdidos:
            print(f"{caso['id']} {caso['pergunta']}")
            for trecho_id in sorted(perdidos):
                posicao = ranking.index(trecho_id) + 1 if trecho_id in ranking else f"> {k_maximo}"
                print(f"  fora do top {K_CRITERIO}: {trecho_id} (posição {posicao})")

    print(f"\n{len(casos)} perguntas com trechos relevantes, {total_relevantes} trechos rotulados")
    for k in CORTES_K:
        micro = encontrados[k] / total_relevantes
        macro = sum(recall_por_pergunta[k]) / len(casos)
        print(f"recall@{k}: {micro:.3f} (média por pergunta: {macro:.3f})")
    passou = encontrados[K_CRITERIO] / total_relevantes >= RECALL_MINIMO
    print(
        f"critério recall@{K_CRITERIO} >= {RECALL_MINIMO}: "
        f"{'passou' if passou else 'NÃO passou'}"
    )


if __name__ == "__main__":
    main()
