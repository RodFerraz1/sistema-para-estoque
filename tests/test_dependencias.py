"""Testes do `resolver` dos scripts, que monta os serviços pela composição da API."""
from __future__ import annotations

from fastapi import Depends

from scripts.dependencias import resolver


class Contador:
    def __init__(self) -> None:
        self.chamadas = 0


contador = Contador()


def get_base() -> str:
    contador.chamadas += 1
    return "base"


def get_meio(base: str = Depends(get_base)) -> str:
    return f"{base}>meio"


def get_topo(meio: str = Depends(get_meio), base: str = Depends(get_base)) -> str:
    return f"{meio}>topo ({base})"


def test_resolve_a_arvore_chamando_cada_dependencia_uma_vez() -> None:
    contador.chamadas = 0

    assert resolver(get_topo) == "base>meio>topo (base)"
    assert contador.chamadas == 1


def test_trocas_substituem_a_dependencia_como_o_dependency_overrides() -> None:
    assert resolver(get_topo, {get_base: lambda: "trocada"}) == "trocada>meio>topo (trocada)"
