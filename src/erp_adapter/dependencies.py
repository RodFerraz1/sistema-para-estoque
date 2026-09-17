"""Dependência FastAPI para injetar o `ERPAdapter`.

Em produção, retorna o `PostgresERPAdapter` conectado ao engine global.
Em testes, sobrescreva via `app.dependency_overrides[get_erp_adapter]`.
"""
from __future__ import annotations

from src.db.engine import get_engine
from src.erp_adapter.port import ERPAdapter
from src.erp_adapter.postgres import PostgresERPAdapter


def get_erp_adapter() -> ERPAdapter:
    return PostgresERPAdapter(get_engine())
