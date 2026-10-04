"""Módulo `catalog`: sabe sobre SKU, produto e fornecedor.

Não sabe sobre estoque, venda ou pedido. Consome apenas o `ERPAdapter`.
"""
from __future__ import annotations

import unicodedata

from uuid import UUID

from src.catalog.schemas import SKU, FornecedorParaSKU
from src.erp_adapter.port import ERPAdapter


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sem_acento.casefold()


def palavras_da_busca(texto: str) -> list[str]:
    return _normalizar(texto).split()


def sku_contem_todas(sku: SKU, palavras: list[str]) -> bool:
    """O código, o nome do produto, a cor ou o tamanho contêm cada uma das `palavras`,
    sem diferenciar acento nem maiúscula. As palavras vêm de `palavras_da_busca`."""
    alvo = _normalizar(f"{sku.sku_code} {sku.produto_nome} {sku.cor} {sku.tamanho}")
    return all(p in alvo for p in palavras)


def ordem_por_nome(sku: SKU) -> tuple[str, str, str]:
    """Nome do produto, cor e tamanho, sem diferenciar acento nem maiúscula."""
    return (_normalizar(sku.produto_nome), _normalizar(sku.cor), _normalizar(sku.tamanho))


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

    def fornecedores_por_sku(self) -> dict[str, list[FornecedorParaSKU]]:
        """`fornecedores_de` dos SKUs ativos numa leitura só. SKU sem fornecedor fica de fora."""
        return self._erp.fornecedores_por_sku()

    def categorias(self) -> list[str]:
        """As categorias com algum SKU ativo, em ordem alfabética."""
        return sorted({sku.categoria for sku in self._erp.listar_skus()})

    def fornecedores_com_sku_ativo(self) -> list[tuple[UUID, str]]:
        """Id e nome dos fornecedores que vendem algum SKU ativo, pelo nome."""
        nomes = {
            f.fornecedor_id: f.fornecedor_nome
            for fornecedores in self._erp.fornecedores_por_sku().values()
            for f in fornecedores
        }
        return sorted(nomes.items(), key=lambda par: _normalizar(par[1]))

    def buscar_skus(self, texto: str, limite: int = 20) -> list[SKU]:
        """SKUs ativos cujo código, nome do produto, cor ou tamanho contêm todas as
        palavras de `texto`, sem diferenciar acento nem maiúscula. Ordem: nome do
        produto, cor e tamanho."""
        palavras = palavras_da_busca(texto)
        if not palavras:
            return []
        achados = [sku for sku in self._erp.listar_skus() if sku_contem_todas(sku, palavras)]
        achados.sort(key=ordem_por_nome)
        return achados[:limite]
