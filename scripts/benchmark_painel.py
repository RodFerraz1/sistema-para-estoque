"""Mede o tempo de `GET /painel` contra o Postgres local, para a meta da spec 09: menos de
2 segundos com 5.000 SKUs ativos e um número fixo de consultas ao banco.

Com `--skus N`, refaz o seed com N SKUs sintéticos a mais antes de medir (apaga e recria
o schema `erp`; 5.000 levam cerca de 70 s). Sem `--skus`, mede o banco como está. Roda o
app no mesmo processo, como um comprador fake, sem login. Sai com erro quando a mediana
passa da meta.

    uv run python -m scripts.benchmark_painel --skus 5000
    uv run python -m scripts.benchmark_painel --vezes 10

Depois de medir com `--skus`, volte o banco ao seed padrão com o reset do README.
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event, text

from scripts.seed import run as run_seed
from src.db.engine import get_engine
from src.main import app
from src.usuarios.dependencies import usuario_atual
from src.usuarios.schemas import Usuario

META_SEGUNDOS = 2.0

COMPRADOR = Usuario(
    id=uuid4(),
    nome="Benchmark",
    email="benchmark@copilot.local",
    senha_hash="",
    papeis=["comprador"],
    ativo=True,
    criado_em=datetime.now(UTC),
    ultimo_acesso_em=None,
)


def _skus_ativos() -> int:
    with get_engine().connect() as conn:
        return conn.execute(text("SELECT count(*) FROM erp.skus WHERE ativo")).scalar_one()


def medir(vezes: int) -> tuple[list[float], int]:
    """Tempo de cada `GET /painel`, em segundos, e as consultas ao banco da última."""
    app.dependency_overrides[usuario_atual] = lambda: COMPRADOR
    consultas = 0

    def contar(*_: object) -> None:
        nonlocal consultas
        consultas += 1

    tempos: list[float] = []
    try:
        with TestClient(app) as client:
            for _ in range(vezes):
                consultas = 0
                event.listen(get_engine(), "before_cursor_execute", contar)
                inicio = time.perf_counter()
                response = client.get("/painel")
                tempos.append(time.perf_counter() - inicio)
                event.remove(get_engine(), "before_cursor_execute", contar)
                response.raise_for_status()
    finally:
        app.dependency_overrides.pop(usuario_atual, None)
    return tempos, consultas


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mede o tempo de GET /painel.")
    parser.add_argument("--skus", type=int, help="refaz o seed com estes SKUs sintéticos a mais antes de medir")
    parser.add_argument("--vezes", type=int, default=5, help="quantas vezes chamar o painel (padrão 5)")
    args = parser.parse_args(argv)

    if args.skus is not None:
        inicio = time.perf_counter()
        run_seed(args.skus)
        print(f"seed com {args.skus} SKUs a mais em {time.perf_counter() - inicio:.0f} s")

    tempos, consultas = medir(args.vezes)
    mediana = statistics.median(tempos)
    print(f"SKUs ativos: {_skus_ativos()}")
    print(f"consultas ao banco por painel: {consultas}")
    print(f"GET /painel em {args.vezes} chamadas: primeira {tempos[0]:.2f} s, mediana {mediana:.2f} s, máxima {max(tempos):.2f} s")
    if mediana >= META_SEGUNDOS:
        print(f"acima da meta de {META_SEGUNDOS:.0f} s")
        return 1
    print(f"dentro da meta de {META_SEGUNDOS:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
