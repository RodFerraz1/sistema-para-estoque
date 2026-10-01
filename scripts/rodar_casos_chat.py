"""Rodada dos casos de `evals/casos.json` pelo chat inteiro (M5, ticket 05).

Monta o `Copilot` pelo mesmo `get_copilot` do `POST /chat` (Jev real, redator
configurado no `.env`, ERP, política e corpus do Postgres) e responde as
perguntas dos casos. Cada
resposta grava um registro de decisão em `copilot.registros_decisao`, como no
chat. Imprime por caso a intenção esperada e a escolhida, a confiança, a faixa,
a ação, os SKUs, os sinais do corpus, os vereditos das citações, o redator, a
duração, o motivo da queda do redator e as contagens da redação, e no fim o total
por faixa, por ação, por veredito e das contagens.

As contagens medem o que o redator faz sem precisar ler a resposta (M8, ticket 02):
colchetes em que nenhuma parte é id de trecho, sinais do corpus com algum trecho de
origem citado e sugestões com a quantidade escrita como no contexto (`1.234`).

    uv run python -m scripts.rodar_casos_chat               # precisa de JEV_KEY, do seed e do corpus ingerido
    uv run python -m scripts.rodar_casos_chat --casos evals/casos_redator.json
    uv run python -m scripts.rodar_casos_chat --respostas   # imprime também o texto de cada resposta
    uv run python -m scripts.rodar_casos_chat --pausa 30    # espera entre os casos (limite de requisições do provedor)
    uv run python -m scripts.rodar_casos_chat --sem-llm     # troca o redator pelo RedatorSemLLM
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from time import perf_counter, sleep

from scripts.dependencias import resolver
from src.ai.dependencies import get_copilot, get_redator
from src.ai.redator import Redator, RedatorIndisponivel, RedatorSemLLM
from src.ai.schemas import RespostaCopilot, SugestaoComSinais
from src.db.config import get_settings

RAIZ = Path(__file__).resolve().parents[1]
CASOS = RAIZ / "evals" / "casos.json"

_HIFENS = "‐-―−-"
_COLCHETE = re.compile(r"\[([^\[\]\n]+)\]|【([^【】\n]+)】")
_ID_DE_TRECHO = re.compile(rf"[\w./{_HIFENS}]+\.md#[\w/~{_HIFENS}]+")


@dataclass(frozen=True)
class Contagens:
    colchetes_sem_id: int = 0
    sinais_citados: int = 0
    sinais: int = 0
    quantidades_no_texto: int = 0
    sugestoes: int = 0

    def __str__(self) -> str:
        return (
            f"colchetes sem id {self.colchetes_sem_id}, sinais citados {self.sinais_citados}/{self.sinais}, "
            f"quantidades no texto {self.quantidades_no_texto}/{self.sugestoes}"
        )


def colchetes_sem_id(texto: str) -> int:
    """Colchetes retos ou lenticulares sem nenhum id de trecho dentro. As marcas da
    verificação (`[<id> - não confirmada]`) têm o id e não contam."""
    return sum(1 for m in _COLCHETE.finditer(texto) if not _ID_DE_TRECHO.search(m.group(1) or m.group(2)))


def sinais_citados(sugestoes: Sequence[SugestaoComSinais], citados: Collection[str]) -> tuple[int, int]:
    """Quantos sinais das sugestões têm algum trecho de origem entre os `citados`, e o total de sinais."""
    sinais = [sinal for s in sugestoes for sinal in s.sinais or []]
    return sum(1 for sinal in sinais if set(sinal.trechos) & set(citados)), len(sinais)


def quantidades_no_texto(sugestoes: Sequence[SugestaoComSinais], texto: str) -> tuple[int, int]:
    """Quantas sugestões têm a quantidade escrita no texto como no contexto (milhar com
    ponto), como número inteiro solto, e o total de sugestões."""
    escritas = sum(1 for s in sugestoes if _numero_solto(s.sugestao.quantidade).search(texto))
    return escritas, len(sugestoes)


def _numero_solto(quantidade: int) -> re.Pattern[str]:
    numero = re.escape(f"{quantidade:,}".replace(",", "."))
    return re.compile(rf"(?<![\d.,]){numero}(?![.,]?\d)")


def contar(resposta: RespostaCopilot) -> Contagens:
    citados, sinais = sinais_citados(resposta.sugestoes, {c.trecho_id for c in resposta.citacoes})
    escritas, sugestoes = quantidades_no_texto(resposta.sugestoes, resposta.resposta)
    return Contagens(colchetes_sem_id(resposta.resposta), citados, sinais, escritas, sugestoes)


def somar(contagens: Iterable[Contagens]) -> Contagens:
    lista = list(contagens)
    return Contagens(**{f.name: sum(getattr(c, f.name) for c in lista) for f in fields(Contagens)})


class RedatorComQuedas(Redator):
    """Repassa ao redator configurado e guarda o motivo da queda, que o `Copilot` troca
    pelo `RedatorSemLLM` sem expor."""

    def __init__(self, redator: Redator) -> None:
        self._redator = redator
        self.queda: str | None = None

    @property
    def nome(self) -> str:
        return self._redator.nome

    @property
    def usa_llm(self) -> bool:
        return self._redator.usa_llm

    def redigir(self, pergunta: str, contexto: str) -> str:
        self.queda = None
        try:
            return self._redator.redigir(pergunta, contexto)
        except RedatorIndisponivel as erro:
            self.queda = str(erro)
            raise


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
        f"     Citações: {_contagem(vereditos) or '-'}\n"
        f"     Contagens: {contar(resposta)}\n"
        f"     {caso['pergunta']}"
    )


def _contagem(contador: Counter[str]) -> str:
    return ", ".join(f"{chave} {n}" for chave, n in contador.most_common())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--casos", type=Path, default=CASOS, help="arquivo de casos (padrão: evals/casos.json)")
    parser.add_argument("--respostas", action="store_true", help="imprime também o texto de cada resposta")
    parser.add_argument("--pausa", type=float, default=0.0, help="segundos de espera entre um caso e o seguinte")
    parser.add_argument("--sem-llm", action="store_true", help="troca o redator pelo RedatorSemLLM")
    args = parser.parse_args()

    if not get_settings().jev_key:
        raise SystemExit("JEV_KEY vazio no .env")
    casos = json.loads(args.casos.read_text(encoding="utf-8"))
    redator = RedatorComQuedas(RedatorSemLLM() if args.sem_llm else get_redator())
    copilot = resolver(get_copilot, {get_redator: lambda: redator})

    faixas: Counter[str] = Counter()
    acoes: Counter[str] = Counter()
    vereditos: Counter[str] = Counter()
    contagens: list[Contagens] = []
    quedas = 0
    acertos = 0
    for i, caso in enumerate(casos):
        if i and args.pausa:
            sleep(args.pausa)
        redator.queda = None
        inicio = perf_counter()
        resposta = copilot.responder(caso["pergunta"])
        print(linha(caso, resposta, perf_counter() - inicio))
        if redator.queda:
            quedas += 1
            print(f"     Queda do redator: {redator.queda}")
        if args.respostas:
            print("\n".join(f"     | {t}" for t in resposta.resposta.splitlines()))
        print()
        faixas[resposta.faixa] += 1
        acoes[resposta.acao] += 1
        vereditos.update(c.veredito for c in resposta.citacoes)
        contagens.append(contar(resposta))
        acertos += resposta.entendimento.intencao.escolha == caso["intencao"]

    total = somar(contagens)
    print(f"Intenção: {acertos}/{len(casos)}")
    print("Faixas: " + ", ".join(f"{f} {faixas[f]}" for f in ("alta", "media", "baixa")))
    print(f"Ações: {_contagem(acoes)}")
    print(f"Citações: {_contagem(vereditos) or 'nenhuma'}")
    print(f"Quedas do redator: {quedas}")
    print(f"Colchetes sem id de trecho: {total.colchetes_sem_id}")
    print(f"Sinais citados: {total.sinais_citados}/{total.sinais}")
    print(f"Quantidades no texto: {total.quantidades_no_texto}/{total.sugestoes}")


if __name__ == "__main__":
    main()
