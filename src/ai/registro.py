"""Registro de decisão: o que fica gravado de cada pergunta respondida pelo chat,
para auditoria e para recalibrar as faixas de confiança (M8)."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.ai.schemas import Acao, Entendimento, Faixa, Intencao, Probabilidade


class RegistroDecisao(BaseModel):
    """`intencao` e `confianca` repetem o `entendimento` para o M8 filtrar sem abrir
    o jsonb. `trechos` são os ids que foram ao redator."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    criado_em: datetime
    pergunta: str
    intencao: Intencao
    confianca: Probabilidade
    faixa: Faixa
    acao: Acao
    skus: list[str]
    entendimento: Entendimento
    trechos: list[str]
    redator: str | None
    resposta: str
    duracao_ms: int


class RegistrosDecisao(Protocol):
    def gravar(self, registro: RegistroDecisao) -> None: ...

    def listar(self, limite: int) -> list[RegistroDecisao]:
        """Os `limite` registros mais recentes, do mais novo para o mais antigo."""
        ...


class InMemoryRegistrosDecisao(RegistrosDecisao):
    def __init__(self) -> None:
        self._registros: list[RegistroDecisao] = []

    def gravar(self, registro: RegistroDecisao) -> None:
        self._registros.append(registro)

    def listar(self, limite: int) -> list[RegistroDecisao]:
        recentes = sorted(reversed(self._registros), key=lambda r: r.criado_em, reverse=True)
        return recentes[:limite]
