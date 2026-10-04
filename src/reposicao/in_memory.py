"""Implementação em memória dos repositórios do módulo `reposicao`, para testes."""
from __future__ import annotations

from collections.abc import Collection
from datetime import datetime
from uuid import UUID

from src.reposicao.repositorio import (
    AvisosGondolaRepositorio,
    CapacidadesGondolaRepositorio,
    SetoresRepositorio,
    SetorJaExiste,
    VerificacoesRepositorio,
)
from src.reposicao.schemas import AvisoGondola, CapacidadeGondola, Setor, SetorDoSku, VerificacaoGondola


class InMemoryVerificacoesRepositorio(VerificacoesRepositorio):
    def __init__(self) -> None:
        self._verificacoes: list[VerificacaoGondola] = []

    def gravar(self, verificacao: VerificacaoGondola) -> None:
        self._verificacoes.append(verificacao)

    def _recentes_primeiro(self, verificacoes: list[VerificacaoGondola]) -> list[VerificacaoGondola]:
        return sorted(verificacoes, key=lambda v: (v.criado_em, str(v.id)), reverse=True)

    def listar(self, sku_code: str) -> list[VerificacaoGondola]:
        return self._recentes_primeiro([v for v in self._verificacoes if v.sku_code == sku_code])

    def dos_skus(self, sku_codes: Collection[str], desde: datetime) -> list[VerificacaoGondola]:
        return self._recentes_primeiro(
            [v for v in self._verificacoes if v.sku_code in sku_codes and v.criado_em >= desde]
        )

    def ultimas(self) -> dict[str, VerificacaoGondola]:
        return {sku_code: self.listar(sku_code)[0] for sku_code in {v.sku_code for v in self._verificacoes}}


class InMemorySetoresRepositorio(SetoresRepositorio):
    def __init__(self) -> None:
        self._setores: dict[UUID, Setor] = {}
        self._dos_skus: dict[str, SetorDoSku] = {}

    def listar(self) -> list[Setor]:
        return sorted(self._setores.values(), key=lambda s: s.nome.casefold())

    def carregar(self, setor_id: UUID) -> Setor | None:
        return self._setores.get(setor_id)

    def gravar(self, setor: Setor) -> None:
        if any(s.nome.lower() == setor.nome.lower() and s.id != setor.id for s in self._setores.values()):
            raise SetorJaExiste(setor.nome)
        self._setores[setor.id] = setor

    def lembrar(self, setor_do_sku: SetorDoSku) -> None:
        self._dos_skus[setor_do_sku.sku_code] = setor_do_sku

    def do_sku(self, sku_code: str) -> SetorDoSku | None:
        return self._dos_skus.get(sku_code)

    def dos_skus(self) -> dict[str, SetorDoSku]:
        return dict(self._dos_skus)


class InMemoryAvisosGondolaRepositorio(AvisosGondolaRepositorio):
    def __init__(self) -> None:
        self._avisos: list[AvisoGondola] = []

    def gravar(self, aviso: AvisoGondola) -> None:
        self._avisos.append(aviso)

    def _recentes_primeiro(self, avisos: list[AvisoGondola]) -> list[AvisoGondola]:
        return sorted(avisos, key=lambda a: (a.criado_em, str(a.id)), reverse=True)

    def listar(self, sku_code: str | None = None) -> list[AvisoGondola]:
        return self._recentes_primeiro([a for a in self._avisos if sku_code is None or a.sku_code == sku_code])

    def do_usuario(self, usuario_id: UUID, desde: datetime) -> list[AvisoGondola]:
        return self._recentes_primeiro(
            [a for a in self._avisos if a.usuario_id == usuario_id and a.criado_em >= desde]
        )


class InMemoryCapacidadesGondolaRepositorio(CapacidadesGondolaRepositorio):
    def __init__(self) -> None:
        self._capacidades: dict[UUID, CapacidadeGondola] = {}

    def gravar(self, capacidade: CapacidadeGondola) -> None:
        self._capacidades[capacidade.produto_id] = capacidade

    def do_produto(self, produto_id: UUID) -> CapacidadeGondola | None:
        return self._capacidades.get(produto_id)

    def todas(self) -> dict[UUID, CapacidadeGondola]:
        return dict(self._capacidades)
