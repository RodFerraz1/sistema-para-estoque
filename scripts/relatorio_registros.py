"""Relatório do registro de decisão (`copilot.registros_decisao`) para a calibração do M8.

Lê os registros pelo port `RegistrosDecisao` e imprime: totais, período e perguntas
distintas; a confiança da intenção por intenção escolhida; as faixas e as ações; as
perguntas medidas mais de uma vez, com a dispersão da confiança; o redator; a duração
por ação; os vereditos de citação perto do `LIMIAR_CITACAO`; e os sinais por tipo.

O registro não tem rótulo de acerto. `--exportar ARQ` grava as perguntas distintas que
não estão em `evals/casos.json` nem em `evals/intencoes.json`, no formato dos casos e
sem a resposta do Jev, para rotular às cegas.

    uv run python -m scripts.relatorio_registros
    uv run python -m scripts.relatorio_registros --exportar /tmp/perguntas.json
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import unicodedata
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import get_args

from src.ai.citacoes import LIMIAR_CITACAO
from src.ai.postgres import PostgresRegistrosDecisao
from src.ai.schemas import Acao, Faixa, Intencao, RegistroDecisao, TipoSinal, Veredito
from src.db.engine import get_engine

RAIZ = Path(__file__).resolve().parents[1]
CONHECIDAS = (RAIZ / "evals" / "casos.json", RAIZ / "evals" / "intencoes.json")
LIMITE_PADRAO = 10_000
DISTANCIA_DO_LIMIAR = 0.10


@dataclass(frozen=True)
class ResumoConfianca:
    quantidade: int
    minima: float
    mediana: float
    maxima: float


@dataclass(frozen=True)
class Repetida:
    pergunta: str
    vezes: int
    intencoes: tuple[Intencao, ...]
    minima: float
    maxima: float

    @property
    def dispersao(self) -> float:
        return round(self.maxima - self.minima, 3)


@dataclass(frozen=True)
class Duracao:
    quantidade: int
    mediana_ms: float
    p90_ms: int


def normalizar_pergunta(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sem_acento).strip().casefold()


def por_pergunta(registros: Iterable[RegistroDecisao]) -> dict[str, list[RegistroDecisao]]:
    """Registros agrupados pela pergunta normalizada, na ordem da primeira vez que ela apareceu."""
    grupos: dict[str, list[RegistroDecisao]] = {}
    for registro in sorted(registros, key=lambda r: r.criado_em):
        grupos.setdefault(normalizar_pergunta(registro.pergunta), []).append(registro)
    return grupos


def confianca_por_intencao(registros: Sequence[RegistroDecisao]) -> dict[Intencao, ResumoConfianca]:
    resumo = {}
    for intencao in get_args(Intencao):
        confiancas = sorted(r.confianca for r in registros if r.intencao == intencao)
        if confiancas:
            resumo[intencao] = ResumoConfianca(
                len(confiancas), confiancas[0], statistics.median(confiancas), confiancas[-1]
            )
    return resumo


def repetidas(registros: Sequence[RegistroDecisao]) -> list[Repetida]:
    """Perguntas medidas mais de uma vez, da maior dispersão da confiança para a menor."""
    resultado = [
        Repetida(
            pergunta=grupo[0].pergunta,
            vezes=len(grupo),
            intencoes=tuple(dict.fromkeys(r.intencao for r in grupo)),
            minima=min(r.confianca for r in grupo),
            maxima=max(r.confianca for r in grupo),
        )
        for grupo in por_pergunta(registros).values()
        if len(grupo) > 1
    ]
    return sorted(resultado, key=lambda r: (-r.dispersao, r.minima))


def duracoes_por_acao(registros: Sequence[RegistroDecisao]) -> dict[Acao, Duracao]:
    duracoes = {}
    for acao in get_args(Acao):
        valores = sorted(r.duracao_ms for r in registros if r.acao == acao)
        if valores:
            duracoes[acao] = Duracao(len(valores), statistics.median(valores), percentil(valores, 90))
    return duracoes


def percentil(valores: Sequence[int], p: int) -> int:
    """Percentil pelo posto mais próximo: o menor valor com pelo menos `p`% da amostra até ele."""
    ordenados = sorted(valores)
    return ordenados[max(math.ceil(p / 100 * len(ordenados)) - 1, 0)]


def vereditos(registros: Sequence[RegistroDecisao]) -> Counter[Veredito]:
    return Counter(c.veredito for r in registros for c in r.citacoes)


def perto_do_limiar(
    registros: Sequence[RegistroDecisao], limiar: float, distancia: float = DISTANCIA_DO_LIMIAR
) -> tuple[int, int]:
    """(perto, avaliadas): quantas citações com confiança do Jev ficam a menos de `distancia`
    do limiar, entre as que têm confiança."""
    confiancas = [c.confianca for r in registros for c in r.citacoes if c.confianca is not None]
    return sum(abs(c - limiar) < distancia for c in confiancas), len(confiancas)


def sinais_por_tipo(registros: Sequence[RegistroDecisao]) -> Counter[TipoSinal]:
    return Counter(sinal.tipo for r in registros for s in r.sinais for sinal in s.sinais or [])


def sugestoes_sem_sinais(registros: Sequence[RegistroDecisao]) -> tuple[int, int]:
    """(com sinais nulos, sugestões): os nulos são as sugestões sem sinais calculados."""
    sugestoes = [s for r in registros for s in r.sinais]
    return sum(s.sinais is None for s in sugestoes), len(sugestoes)


def perguntas_para_exportar(registros: Sequence[RegistroDecisao], conhecidas: Iterable[str]) -> list[dict]:
    """Perguntas distintas fora de `conhecidas`, no formato dos casos e sem a resposta do Jev."""
    ja_rotuladas = {normalizar_pergunta(p) for p in conhecidas}
    novas = [g[0].pergunta for chave, g in por_pergunta(registros).items() if chave not in ja_rotuladas]
    return [
        {"id": f"r{n:02d}", "pergunta": pergunta, "intencao": None, "produtos_aceitos": None}
        for n, pergunta in enumerate(novas, start=1)
    ]


def relatorio(registros: Sequence[RegistroDecisao], limiar_citacao: float = LIMIAR_CITACAO) -> str:
    if not registros:
        return "Nenhum registro de decisão."
    inicio = min(r.criado_em for r in registros)
    fim = max(r.criado_em for r in registros)
    linhas = [
        f"Registros: {len(registros)}, de {inicio:%Y-%m-%d %H:%M} a {fim:%Y-%m-%d %H:%M} (UTC)",
        f"Perguntas distintas: {len(por_pergunta(registros))}",
        "\nConfiança da intenção por intenção escolhida (quantidade, mínima, mediana, máxima):",
    ]
    for intencao, resumo in confianca_por_intencao(registros).items():
        linhas.append(
            f"  {intencao:<23} {resumo.quantidade:>4}  {resumo.minima:.2f}  {resumo.mediana:.2f}  {resumo.maxima:.2f}"
        )
    linhas.append(f"\nFaixas: {_contagens(Counter(r.faixa for r in registros), get_args(Faixa))}")
    linhas.append(f"Ações: {_contagens(Counter(r.acao for r in registros), get_args(Acao))}")

    linhas.append("\nPerguntas medidas mais de uma vez (vezes, confiança mínima-máxima, dispersão, intenções):")
    for repetida in repetidas(registros):
        linhas.append(
            f"  {repetida.vezes:>3}x  {repetida.minima:.2f}-{repetida.maxima:.2f}  {repetida.dispersao:.2f}  "
            f"{'/'.join(repetida.intencoes)}: {repetida.pergunta}"
        )

    redatores = Counter(r.redator or "sem redação (resposta em código)" for r in registros)
    linhas.append(f"\nRedator: {_contagens(redatores)}")
    linhas.append("Duração por ação (quantidade, mediana e p90 em ms):")
    for acao, duracao in duracoes_por_acao(registros).items():
        linhas.append(f"  {acao:<23} {duracao.quantidade:>4}  {duracao.mediana_ms:>8.0f}  {duracao.p90_ms:>6}")

    perto, avaliadas = perto_do_limiar(registros, limiar_citacao)
    linhas.append(f"\nVereditos de citação: {_contagens(vereditos(registros), get_args(Veredito))}")
    linhas.append(
        f"  {perto} de {avaliadas} confianças a menos de {DISTANCIA_DO_LIMIAR:.2f} "
        f"do LIMIAR_CITACAO ({limiar_citacao:.2f})"
    )
    nulos, sugestoes = sugestoes_sem_sinais(registros)
    linhas.append(f"Sinais por tipo: {_contagens(sinais_por_tipo(registros), get_args(TipoSinal))}")
    linhas.append(f"  {nulos} de {sugestoes} sugestões com sinais nulos (Jev fora do ar)")
    return "\n".join(linhas)


def _contagens(contagem: Counter[str], ordem: Iterable[str] | None = None) -> str:
    chaves: Iterable[str] = ordem if ordem is not None else [c for c, _ in contagem.most_common()]
    return ", ".join(f"{chave} {contagem[chave]}" for chave in chaves)


def perguntas_conhecidas(arquivos: Iterable[Path]) -> list[str]:
    return [
        caso["pergunta"]
        for arquivo in arquivos
        if arquivo.exists()
        for caso in json.loads(arquivo.read_text(encoding="utf-8"))
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limite", type=int, default=LIMITE_PADRAO, help="quantos registros ler, dos mais novos")
    parser.add_argument("--exportar", type=Path, metavar="ARQ", help="grava as perguntas novas para rotular às cegas")
    args = parser.parse_args()

    registros = PostgresRegistrosDecisao(get_engine()).listar(args.limite)
    print(relatorio(registros))
    if len(registros) == args.limite:
        print(f"\nAtenção: o limite de {args.limite} registros foi atingido; aumente --limite.")
    if args.exportar:
        perguntas = perguntas_para_exportar(registros, perguntas_conhecidas(CONHECIDAS))
        args.exportar.write_text(json.dumps(perguntas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\n{len(perguntas)} perguntas exportadas para {args.exportar}")


if __name__ == "__main__":
    main()
