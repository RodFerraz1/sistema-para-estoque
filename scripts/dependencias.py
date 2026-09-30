"""Dependências FastAPI resolvidas fora de uma requisição, para os scripts montarem
os serviços com a mesma composição da API."""
from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from typing import Any

from fastapi.params import Depends


def resolver[T](
    dependencia: Callable[..., T], trocas: Mapping[Callable[..., Any], Callable[[], Any]] | None = None
) -> T:
    """Chama `dependencia` resolvendo os parâmetros `Depends(...)` como o FastAPI numa
    requisição: cada dependência roda uma vez só, e `trocas` faz o papel do
    `app.dependency_overrides`."""
    trocas = trocas or {}
    resolvidas: dict[Callable[..., Any], Any] = {}

    def resolver_uma(dep: Callable[..., Any]) -> Any:
        if dep not in resolvidas:
            if dep in trocas:
                resolvidas[dep] = trocas[dep]()
            else:
                resolvidas[dep] = dep(
                    **{
                        nome: resolver_uma(parametro.default.dependency)
                        for nome, parametro in inspect.signature(dep).parameters.items()
                        if isinstance(parametro.default, Depends)
                    }
                )
        return resolvidas[dep]

    return resolver_uma(dependencia)
