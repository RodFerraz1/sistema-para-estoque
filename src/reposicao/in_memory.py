"""Implementação em memória do repositório do módulo `reposicao`, para testes."""
from __future__ import annotations

from src.reposicao.repositorio import VerificacoesRepositorio
from src.reposicao.schemas import VerificacaoGondola


class InMemoryVerificacoesRepositorio(VerificacoesRepositorio):
    def __init__(self) -> None:
        self._verificacoes: list[VerificacaoGondola] = []

    def gravar(self, verificacao: VerificacaoGondola) -> None:
        self._verificacoes.append(verificacao)

    def listar(self, sku_code: str) -> list[VerificacaoGondola]:
        do_sku = [v for v in self._verificacoes if v.sku_code == sku_code]
        return sorted(do_sku, key=lambda v: (v.criado_em, str(v.id)), reverse=True)

    def ultimas(self) -> dict[str, VerificacaoGondola]:
        return {sku_code: self.listar(sku_code)[0] for sku_code in {v.sku_code for v in self._verificacoes}}
