"""Avaliação do entendimento da pergunta do chat contra o Jev real (M5, ticket 01; M8, ticket 03).

Roda `JevDecisionModel.entender_pergunta` nos casos de um ou mais arquivos (`--casos`,
padrão `evals/casos.json`, ids únicos entre eles), com os produtos do catálogo lidos do
banco (seed), grava as respostas cruas e imprime, por arquivo e no total, o acerto da
intenção e o acerto do produto (escolha dentro de `produtos_aceitos`), mais a varredura
do limiar do produto, só para leitura.

Os limiares saem da regra de calibração do M8 (`scripts/calibracao.py`):

- `LIMIAR_PRODUTO`, com erro crítico: produto errado usado (escolha diferente de
  `nenhum` fora de `produtos_aceitos`). Com menos de 3 erros, o limiar atual fica.
- `FAIXAS.media`, sem erro crítico: positivos são as intenções certas e negativos as
  erradas, contadas uma vez por pergunta distinta (a primeira vez que ela aparece).
- `FAIXAS.alta`, com erro crítico: intenção errada com confiança de pelo menos a
  `alta` atual. Sem esse erro, a `alta` fica.

Se a `media` sair maior ou igual à `alta`, as faixas ficam e o relatório avisa.

    uv run python -m scripts.avaliar_entendimento          # chama o Jev (precisa de JEV_KEY e do seed)
    uv run python -m scripts.avaliar_entendimento --casos evals/casos.json evals/intencoes.json --rotulo antes
    uv run python -m scripts.avaliar_entendimento --de-arquivo evals/resultados/entendimento-AAAA-MM-DD.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from time import perf_counter

from scripts.calibracao import Calibracao, calibrar, calibrar_erro_critico, descrever, formatar_limiar
from scripts.relatorio_registros import normalizar_pergunta
from src.ai.chat import FAIXAS
from src.ai.decisao import DecisionModel
from src.ai.identificacao import LIMIAR_PRODUTO, produtos_do_catalogo
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


@dataclass(frozen=True)
class PontoVarredura:
    limiar: float
    certos: int
    errados: int


@dataclass(frozen=True)
class CalibracaoFaixas:
    media: Calibracao
    alta: Calibracao

    @property
    def em_conflito(self) -> bool:
        return self.media.limiar >= self.alta.limiar


def carregar_casos(arquivos: Sequence[Path]) -> dict[str, list[dict]]:
    """Casos por nome de arquivo, na ordem dada. Recusa id repetido entre os arquivos."""
    por_arquivo = {arquivo.name: json.loads(arquivo.read_text(encoding="utf-8")) for arquivo in arquivos}
    ids = Counter(caso["id"] for casos in por_arquivo.values() for caso in casos)
    repetidos = sorted(id_ for id_, vezes in ids.items() if vezes > 1)
    if repetidos:
        raise ValueError(f"ids repetidos entre os arquivos de casos: {', '.join(repetidos)}")
    return por_arquivo


def nome_do_resultado(dia: date, rotulo: str | None) -> str:
    return f"entendimento-{dia.isoformat()}{f'-{rotulo}' if rotulo else ''}.json"


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
        usados = [c for c in _com_produto(casos, por_caso) if por_caso[c["id"]].produto.confianca >= limiar]
        certos = sum(_produto_certo(c, por_caso[c["id"]]) for c in usados)
        pontos.append(PontoVarredura(limiar, certos, len(usados) - certos))
    return pontos


def calibrar_produto(casos: list[dict], por_caso: dict[str, Entendimento]) -> Calibracao:
    def confiancas(certo: bool) -> list[float]:
        return [
            por_caso[c["id"]].produto.confianca
            for c in _com_produto(casos, por_caso)
            if _produto_certo(c, por_caso[c["id"]]) == certo
        ]

    return calibrar_erro_critico(erros=confiancas(False), acertos=confiancas(True), atual=LIMIAR_PRODUTO)


def calibrar_faixas(casos: list[dict], por_caso: dict[str, Entendimento]) -> CalibracaoFaixas:
    certas: list[float] = []
    erradas: list[float] = []
    distintos: dict[str, dict] = {}
    for caso in casos:
        distintos.setdefault(normalizar_pergunta(caso["pergunta"]), caso)
    for caso in distintos.values():
        intencao = por_caso[caso["id"]].intencao
        (certas if intencao.escolha == caso["intencao"] else erradas).append(intencao.confianca)
    return CalibracaoFaixas(
        media=calibrar(positivos=certas, negativos=erradas, atual=FAIXAS.media),
        alta=calibrar_erro_critico(
            erros=[confianca for confianca in erradas if confianca >= FAIXAS.alta], acertos=certas, atual=FAIXAS.alta
        ),
    )


def _com_produto(casos: list[dict], por_caso: dict[str, Entendimento]) -> list[dict]:
    return [c for c in casos if por_caso[c["id"]].produto.escolha != NENHUM_PRODUTO]


def _produto_certo(caso: dict, entendimento: Entendimento) -> bool:
    return entendimento.produto.escolha in caso["produtos_aceitos"]


def relatorio(resultado: dict, por_arquivo: dict[str, list[dict]]) -> str:
    por_caso = entendimentos(resultado)
    todos = [caso for casos in por_arquivo.values() for caso in casos]
    linhas = [f"Modelo: {', '.join(sorted({e.modelo for e in por_caso.values()}))}"]
    latencias = sorted(r["latencia_s"] for r in resultado["respostas"])
    linhas.append(f"Latência: mediana {latencias[len(latencias) // 2]:.3f} s, máxima {latencias[-1]:.3f} s")

    for arquivo, casos in por_arquivo.items():
        erros = erros_de_intencao(casos, por_caso)
        linhas.append(f"\nIntenção ({arquivo}): {len(casos) - len(erros)}/{len(casos)}")
        for caso, e in erros:
            linhas.append(
                f"  {caso['id']} esperado {caso['intencao']}, veio {e.intencao.escolha} "
                f"(confiança {e.intencao.confianca:.2f}): {caso['pergunta']}"
            )
    if len(por_arquivo) > 1:
        linhas.append(f"Intenção (total): {len(todos) - len(erros_de_intencao(todos, por_caso))}/{len(todos)}")

    for arquivo, casos in por_arquivo.items():
        erros = erros_de_produto(casos, por_caso)
        linhas.append(f"\nProduto ({arquivo}): {len(casos) - len(erros)}/{len(casos)}")
        for caso in casos:
            e = por_caso[caso["id"]]
            marca = "ok  " if _produto_certo(caso, e) else "ERRO"
            linhas.append(
                f"  {marca} {caso['id']} {e.produto.escolha} (confiança {e.produto.confianca:.2f}); "
                f"aceitos: {', '.join(caso['produtos_aceitos'])}"
            )
    if len(por_arquivo) > 1:
        linhas.append(f"Produto (total): {len(todos) - len(erros_de_produto(todos, por_caso))}/{len(todos)}")

    linhas.append("\nVarredura do limiar do produto (produtos usados, sem contar `nenhum`):")
    linhas.append("  limiar  certos  errados")
    for ponto in varrer_limiar_produto(todos, por_caso):
        linhas.append(f"  {ponto.limiar:.2f}    {ponto.certos:>6}  {ponto.errados:>7}")
    produto = calibrar_produto(todos, por_caso)
    linhas.append(f"\nRegra de calibração do produto: {descrever(produto)}")
    linhas.append(f"LIMIAR_PRODUTO = {formatar_limiar(produto.limiar)}")

    faixas = calibrar_faixas(todos, por_caso)
    linhas.append(f"\nRegra de calibração de FAIXAS.media: {descrever(faixas.media)}")
    linhas.append(f"Regra de calibração de FAIXAS.alta: {descrever(faixas.alta)}")
    if faixas.em_conflito:
        linhas.append(
            f"media {formatar_limiar(faixas.media.limiar)} >= alta {formatar_limiar(faixas.alta.limiar)}: "
            f"as faixas ficam (alta {formatar_limiar(FAIXAS.alta)}, media {formatar_limiar(FAIXAS.media)}) "
            "e o dev decide"
        )
    else:
        linhas.append(
            f"FAIXAS = FaixasConfianca(alta={formatar_limiar(faixas.alta.limiar)}, "
            f"media={formatar_limiar(faixas.media.limiar)})"
        )
    return "\n".join(linhas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--casos", type=Path, nargs="+", default=[CASOS], help="arquivos de casos (padrão: evals/casos.json)")
    parser.add_argument("--rotulo", help="sufixo no nome do resultado: entendimento-<data>-<rotulo>.json")
    parser.add_argument("--de-arquivo", type=Path, help="recalcula as métricas de um resultado gravado, sem chamar o Jev")
    args = parser.parse_args()

    try:
        por_arquivo = carregar_casos(args.casos)
    except ValueError as erro:
        raise SystemExit(str(erro)) from erro
    casos = [caso for casos in por_arquivo.values() for caso in casos]
    if args.de_arquivo:
        resultado = json.loads(args.de_arquivo.read_text(encoding="utf-8"))
        sem_resposta = {c["id"] for c in casos} - {r["caso"] for r in resultado["respostas"]}
        if sem_resposta:
            raise SystemExit(f"casos sem resposta em {args.de_arquivo}: {', '.join(sorted(sem_resposta))}")
    else:
        settings = get_settings()
        if not settings.jev_key:
            raise SystemExit("JEV_KEY vazio no .env")
        arquivo = RESULTADOS / nome_do_resultado(date.today(), args.rotulo)
        if arquivo.exists():
            raise SystemExit(f"{arquivo} já existe; use --de-arquivo para recalcular")
        produtos = produtos_do_catalogo(Catalog(PostgresERPAdapter(get_engine())).listar_skus())
        with criar_cliente(settings.jev_key, settings.jev_model) as cliente:
            respostas = rodar(JevDecisionModel(cliente), casos, produtos)
        resultado = {
            "executado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "modelo_pedido": settings.jev_model,
            "casos": list(por_arquivo),
            "perguntas": {
                "intencao": PERGUNTA_INTENCAO.model_dump(),
                "produto": pergunta_produto(produtos).model_dump(),
            },
            "respostas": respostas,
        }
        RESULTADOS.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Respostas cruas em {arquivo.relative_to(RAIZ)}", file=sys.stderr)

    print(relatorio(resultado, por_arquivo))


if __name__ == "__main__":
    main()
