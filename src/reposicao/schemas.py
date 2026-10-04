"""DTOs de domínio do módulo `reposicao`."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from src.catalog.schemas import SKU


class DiaObservado(BaseModel):
    model_config = ConfigDict(frozen=True)

    dia: date
    quantidade: int


class QuedaDeVenda(BaseModel):
    """A venda de um SKU nos últimos dias abertos ficou muito abaixo da venda diária base.
    `ultimos_dias` é a janela observada, do mais antigo ao mais recente. `probabilidade` é a
    chance de vender no máximo o que vendeu se a venda seguisse a base."""

    model_config = ConfigDict(frozen=True)

    sku_code: str
    venda_diaria_base: float
    ultimos_dias: list[DiaObservado]
    probabilidade: float

    @property
    def vendido_na_janela(self) -> int:
        return sum(d.quantidade for d in self.ultimos_dias)

    @property
    def venda_perdida(self) -> float:
        """O que a base esperava vender na janela menos o que vendeu."""
        return self.venda_diaria_base * len(self.ultimos_dias) - self.vendido_na_janela


class ItemQuedaDeVenda(BaseModel):
    """SKU com queda de venda e estoque disponível: provavelmente falta na gôndola."""

    model_config = ConfigDict(frozen=True)

    sku: SKU
    disponivel: int
    queda: QuedaDeVenda


class FiltroReposicao(BaseModel):
    """Vazio, não filtra. `busca` segue a regra do `catalog.buscar_skus`."""

    model_config = ConfigDict(frozen=True)

    busca: str | None = None
    categoria: str | None = None


class PainelDoRepositor(BaseModel):
    """`quedas_de_venda` vem da maior venda perdida para a menor."""

    model_config = ConfigDict(frozen=True)

    quedas_de_venda: list[ItemQuedaDeVenda]
