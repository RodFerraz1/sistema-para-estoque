"""Módulo `catalog`: sabe sobre SKU, produto e fornecedor.

Não sabe sobre estoque, venda ou pedido. Consome apenas o `ERPAdapter`.
"""
from __future__ import annotations

import unicodedata

from src.catalog.schemas import SKU, FornecedorParaSKU
from src.erp_adapter.port import ERPAdapter


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sem_acento.casefold()


def _contem_todas(sku: SKU, palavras: list[str]) -> bool:
    alvo = _normalizar(f"{sku.sku_code} {sku.produto_nome} {sku.cor} {sku.tamanho}")
    return all(p in alvo for p in palavras)


class Catalog:
    def __init__(self, erp: ERPAdapter) -> None:
        self._erp = erp

    def carregar_sku(self, sku_code: str) -> SKU | None:
        return self._erp.carregar_sku(sku_code)

    def listar_skus(self) -> list[SKU]:
        """SKUs ativos, ordenados por `sku_code`."""
        return self._erp.listar_skus()

    def fornecedores_de(self, sku_code: str) -> list[FornecedorParaSKU]:
        return self._erp.fornecedores_de(sku_code)

    def buscar_skus(self, texto: str, limite: int = 20) -> list[SKU]:
        """SKUs ativos cujo código, nome do produto, cor ou tamanho contêm todas as
        palavras de `texto`, sem diferenciar acento nem maiúscula. Ordem: nome do
        produto, cor e tamanho."""
        palavras = _normalizar(texto).split()
        if not palavras:
            return []
        achados = [sku for sku in self._erp.listar_skus() if _contem_todas(sku, palavras)]
        achados.sort(key=lambda s: (_normalizar(s.produto_nome), _normalizar(s.cor), _normalizar(s.tamanho)))
        return achados[:limite]
