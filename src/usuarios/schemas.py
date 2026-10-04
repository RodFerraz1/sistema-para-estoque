"""DTOs de domínio do módulo `usuarios` (ADR-0007)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict

Papel = Literal["comprador", "vendas", "reposicao", "admin"]
PAPEIS: tuple[Papel, ...] = get_args(Papel)


class Usuario(BaseModel):
    """Pessoa que entra no Copilot. O `email` fica em minúsculas e é único. Uma pessoa
    pode ter mais de um papel. `notificacoes_vistas_ate` é o cursor das notificações: as
    abertas depois dele são não lidas (nulo: nenhuma foi vista)."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    nome: str
    email: str
    senha_hash: str
    papeis: list[Papel]
    ativo: bool
    criado_em: datetime
    ultimo_acesso_em: datetime | None
    notificacoes_vistas_ate: datetime | None = None


class Sessao(BaseModel):
    """Sessão aberta no login. Só o hash do token fica guardado: o token vai no cookie."""

    model_config = ConfigDict(frozen=True)

    token_hash: str
    usuario_id: UUID
    criada_em: datetime
    expira_em: datetime
    revogada_em: datetime | None
