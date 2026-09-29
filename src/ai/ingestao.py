"""Ingestão idempotente do corpus no repositório de trechos.

O hash do conteúdo de cada documento decide o que fazer: igual ao gravado é
pulado, diferente tem todos os trechos substituídos, e o que sumiu da pasta
é removido. Documento sem nenhum trecho conta como ausente. Todos os
documentos são lidos e validados antes da primeira escrita, então um
documento inválido não deixa o índice pela metade.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from src.ai.corpus import ler_documentos, trechos_do_documento
from src.ai.embeddings import Embedder
from src.ai.repositorio import TrechosRepositorio
from src.ai.schemas import RelatorioIngestao, Trecho, TrechoIndexado


def ingerir(
    pasta: Path, embedder: Embedder, repositorio: TrechosRepositorio
) -> RelatorioIngestao:
    conteudos = ler_documentos(pasta)
    lidos = {d: trechos_do_documento(d, conteudo) for d, conteudo in conteudos.items()}
    trechos = {documento: t for documento, t in lidos.items() if t}
    documentos = list(trechos)
    hashes = {documento: _hash(conteudos[documento]) for documento in documentos}
    gravados = repositorio.hashes_por_documento()

    novos = [d for d in documentos if d not in gravados]
    alterados = [d for d in documentos if d in gravados and gravados[d] != hashes[d]]
    inalterados = [d for d in documentos if gravados.get(d) == hashes[d]]
    removidos = sorted(set(gravados) - set(documentos))

    for documento in [*novos, *alterados]:
        repositorio.substituir_documento(
            documento, hashes[documento], _indexar(trechos[documento], embedder)
        )
    for documento in removidos:
        repositorio.remover_documento(documento)

    return RelatorioIngestao(
        novos=novos,
        alterados=alterados,
        removidos=removidos,
        inalterados=inalterados,
        total_trechos=sum(len(t) for t in trechos.values()),
    )


def _indexar(trechos: list[Trecho], embedder: Embedder) -> list[TrechoIndexado]:
    vetores = embedder.embed([trecho.texto for trecho in trechos])
    return [
        TrechoIndexado(**trecho.model_dump(), embedding=vetor)
        for trecho, vetor in zip(trechos, vetores, strict=True)
    ]


def _hash(conteudo: str) -> str:
    return hashlib.sha256(conteudo.encode()).hexdigest()
