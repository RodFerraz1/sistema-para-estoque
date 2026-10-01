"""Regra de calibração dos limiares do M8 (`.scratch/refinamentos/spec.md`, ticket 04).

A entrada são as probabilidades ou confianças que o Jev deu aos casos rotulados.
Positivos são os que o limiar deve deixar passar e negativos os que deve barrar.

1. Amostra mínima: pelo menos 3 positivos e 3 negativos. Sem isso, o limiar atual fica
   (`amostra_insuficiente`).
2. Separável (maior negativo abaixo do menor positivo): o ponto médio entre os dois
   (`ponto_medio`).
3. Não separável: o meio da faixa de limiares com mais acertos (`mais_acertos`). As
   faixas vão de um valor da amostra ao seguinte, com 0 e 1 nas pontas; no empate
   entre faixas separadas, fica a mais larga e, entre as igualmente largas, a mais
   perto do limiar atual.
4. Erro crítico (`calibrar_erro_critico`): os negativos são só os casos que cometeriam
   o erro que não pode acontecer, e o limiar é o ponto médio entre o erro de maior
   confiança e o acerto de menor confiança acima dele (ou 1, sem acerto acima). Pede
   pelo menos 3 erros críticos (`erro_critico`).

O ponto médio vira o múltiplo de 0,05 mais próximo que ainda fica estritamente entre
os dois lados (a mesma distância de dois, o maior); se nenhum couber, o ponto médio
com duas casas, ou com três quando duas cairiam num dos lados. Como o limiar nunca
coincide com um valor da amostra, tanto faz o limiar ser estrito ou não. A folga é a
distância do limiar a cada lado.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

Regra = Literal["amostra_insuficiente", "ponto_medio", "mais_acertos", "erro_critico"]

AMOSTRA_MINIMA = 3
PASSO = 0.05


@dataclass(frozen=True)
class Calibracao:
    limiar: float
    regra: Regra
    motivo: str
    atual: float
    lados: tuple[float, float] | None = None

    @property
    def folga(self) -> tuple[float, float] | None:
        if self.lados is None:
            return None
        baixo, alto = self.lados
        return round(self.limiar - baixo, 3), round(alto - self.limiar, 3)


def calibrar(positivos: Sequence[float], negativos: Sequence[float], atual: float) -> Calibracao:
    if len(positivos) < AMOSTRA_MINIMA or len(negativos) < AMOSTRA_MINIMA:
        return Calibracao(
            atual,
            "amostra_insuficiente",
            f"{_contagem(len(positivos), 'positivo')} e {_contagem(len(negativos), 'negativo')}; "
            f"a regra pede pelo menos {AMOSTRA_MINIMA} de cada",
            atual,
        )
    if max(negativos) < min(positivos):
        lados = (max(negativos), min(positivos))
        return Calibracao(_entre(*lados), "ponto_medio", f"separável entre {_lados(lados)}", atual, lados)

    def acertos(baixo: float, alto: float) -> int:
        return sum(p >= alto for p in positivos) + sum(n <= baixo for n in negativos)

    faixas = list(pairwise(sorted({0.0, 1.0, *positivos, *negativos})))
    mais = max(acertos(*faixa) for faixa in faixas)
    empatadas = [faixa for faixa in faixas if acertos(*faixa) == mais]
    lados = min(empatadas, key=lambda f: (-round(f[1] - f[0], 6), abs((f[0] + f[1]) / 2 - atual)))
    motivo = f"{mais}/{len(positivos) + len(negativos)} acertos entre {_lados(lados)}"
    if len(empatadas) > 1:
        motivo += f", a faixa mais larga de {len(empatadas)} empatadas"
    return Calibracao(_entre(*lados), "mais_acertos", motivo, atual, lados)


def calibrar_erro_critico(erros: Sequence[float], acertos: Sequence[float], atual: float) -> Calibracao:
    if len(erros) < AMOSTRA_MINIMA:
        return Calibracao(
            atual,
            "amostra_insuficiente",
            f"{_contagem(len(erros), 'erro crítico', 'erros críticos')}; a regra pede pelo menos {AMOSTRA_MINIMA}",
            atual,
        )
    maior_erro = max(erros)
    acima = min((a for a in acertos if a > maior_erro), default=1.0)
    if not maior_erro < acima:
        return Calibracao(
            atual,
            "erro_critico",
            f"erro crítico com confiança {formatar_limiar(maior_erro)}, que nenhum limiar barra; o atual fica",
            atual,
        )
    lados = (maior_erro, acima)
    return Calibracao(
        _entre(*lados),
        "erro_critico",
        f"{len(erros)} erros críticos; entre o maior erro e o menor acerto acima dele, {_lados(lados)}",
        atual,
        lados,
    )


def descrever(calibracao: Calibracao) -> str:
    folga = calibracao.folga
    partes = [calibracao.regra]
    if folga is not None:
        partes.append(f"folga {formatar_limiar(folga[0])} abaixo e {formatar_limiar(folga[1])} acima")
    return (
        f"{formatar_limiar(calibracao.limiar)} ({', '.join(partes)}; {calibracao.motivo}; "
        f"atual {formatar_limiar(calibracao.atual)})"
    )


def formatar_limiar(valor: float) -> str:
    return f"{valor:.2f}" if round(valor, 2) == valor else f"{valor:.3f}"


def _entre(baixo: float, alto: float) -> float:
    meio = (baixo + alto) / 2
    multiplos = [m for k in range(round(1 / PASSO) + 1) if baixo < (m := round(k * PASSO, 2)) < alto]
    if multiplos:
        return min(multiplos, key=lambda m: (round(abs(m - meio), 6), -m))
    limiar = round(meio, 2)
    return limiar if baixo < limiar < alto else round(meio, 3)


def _contagem(quantidade: int, singular: str, plural: str | None = None) -> str:
    return f"{quantidade} {singular if quantidade == 1 else plural or singular + 's'}"


def _lados(lados: tuple[float, float]) -> str:
    return f"{formatar_limiar(lados[0])} e {formatar_limiar(lados[1])}"
