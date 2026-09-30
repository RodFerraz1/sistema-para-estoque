"""Port do registro de decisão: o que fica gravado de cada pergunta respondida pelo
chat, para auditoria e para recalibrar as faixas de confiança (M8)."""
from __future__ import annotations

from typing import Protocol

from src.ai.schemas import RegistroDecisao


class RegistrosDecisao(Protocol):
    def gravar(self, registro: RegistroDecisao) -> None: ...

    def listar(self, limite: int) -> list[RegistroDecisao]:
        """Os `limite` registros mais recentes, do mais novo para o mais antigo."""
        ...
