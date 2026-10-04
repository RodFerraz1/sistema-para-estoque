"""Ports de persistência do módulo `reposicao`. As verificações de gôndola e os avisos de
gôndola vazia são append-only; os setores e o setor conhecido de cada SKU mudam."""
from __future__ import annotations

from collections.abc import Collection
from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.reposicao.schemas import AvisoGondola, Setor, SetorDoSku, VerificacaoGondola


class SetorJaExiste(Exception):
    def __init__(self, nome: str) -> None:
        super().__init__(f"Já existe um setor chamado {nome}.")
        self.nome = nome


class VerificacoesRepositorio(Protocol):
    def gravar(self, verificacao: VerificacaoGondola) -> None: ...

    def listar(self, sku_code: str) -> list[VerificacaoGondola]:
        """As verificações do SKU, da mais recente para a mais antiga (o `id` desempata)."""
        ...

    def dos_skus(self, sku_codes: Collection[str], desde: datetime) -> list[VerificacaoGondola]:
        """As verificações dos SKUs registradas a partir de `desde`, da mais recente para a
        mais antiga (o `id` desempata)."""
        ...

    def ultimas(self) -> dict[str, VerificacaoGondola]:
        """A verificação mais recente de cada SKU que tem alguma, pelo `sku_code`."""
        ...


class SetoresRepositorio(Protocol):
    def listar(self) -> list[Setor]:
        """Todos, ativos ou não, pelo nome."""
        ...

    def carregar(self, setor_id: UUID) -> Setor | None: ...

    def gravar(self, setor: Setor) -> None:
        """Cria ou atualiza pelo `id`. Lança `SetorJaExiste` com o nome de outro setor, sem
        diferenciar maiúsculas."""
        ...

    def lembrar(self, setor_do_sku: SetorDoSku) -> None:
        """Grava o setor conhecido do SKU, no lugar do anterior."""
        ...

    def do_sku(self, sku_code: str) -> SetorDoSku | None: ...

    def dos_skus(self) -> dict[str, SetorDoSku]:
        """O setor conhecido de cada SKU que tem um, pelo `sku_code`."""
        ...


class AvisosGondolaRepositorio(Protocol):
    def gravar(self, aviso: AvisoGondola) -> None: ...

    def listar(self, sku_code: str | None = None) -> list[AvisoGondola]:
        """Os avisos do SKU, ou de todos sem `sku_code`, do mais recente para o mais
        antigo (o `id` desempata)."""
        ...

    def do_usuario(self, usuario_id: UUID, desde: datetime) -> list[AvisoGondola]:
        """Os avisos do usuário registrados a partir de `desde`, do mais recente para o
        mais antigo (o `id` desempata)."""
        ...
