"""DTOs de domínio do módulo `notificacoes`."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.usuarios.schemas import Papel

TipoEpisodio = Literal[
    "ruptura",
    "entrega_atrasada",
    "aviso",
    "queda_de_venda",
    "estoque_divergente",
    "decisao_sobre_aviso",
    "gondola_vazia",
    "verificacao_sobre_aviso",
]


class Condicao(BaseModel):
    """O que vale agora para um SKU ou para um pedido. A condição é o `tipo` com o
    `sku_code` e o `pedido_id`; `detalhe` guarda os números do momento, em JSON."""

    model_config = ConfigDict(frozen=True)

    tipo: TipoEpisodio
    sku_code: str | None = None
    pedido_id: UUID | None = None
    papel_destino: Papel
    detalhe: dict[str, Any] = {}

    @property
    def chave(self) -> tuple[str, str | None, UUID | None]:
        return (self.tipo, self.sku_code, self.pedido_id)


class Episodio(BaseModel):
    """Intervalo em que uma condição valeu. Aberto enquanto `fechado_em` é nulo. Um evento
    de uma vez só, como o aviso da equipe de vendas, nasce fechado."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    tipo: TipoEpisodio
    sku_code: str | None
    pedido_id: UUID | None
    papel_destino: Papel
    aberto_em: datetime
    fechado_em: datetime | None
    detalhe: dict[str, Any]

    @property
    def chave(self) -> tuple[str, str | None, UUID | None]:
        return (self.tipo, self.sku_code, self.pedido_id)


class Notificacao(BaseModel):
    """Um episódio visto por um usuário do papel de destino."""

    model_config = ConfigDict(frozen=True)

    episodio: Episodio
    lida: bool


class CaixaDeNotificacoes(BaseModel):
    """As notificações mais recentes primeiro e o total de não lidas, que pode passar do
    tamanho da lista."""

    model_config = ConfigDict(frozen=True)

    notificacoes: list[Notificacao]
    nao_lidas: int
