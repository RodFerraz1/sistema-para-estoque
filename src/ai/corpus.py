"""Leitura do corpus em trechos, um por seção de markdown."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from src.ai.schemas import Trecho

_PADRAO_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
_PADRAO_TITULO = re.compile(r"^(#{1,3}) +(.+?) *$")
_SLUG_INTRODUCAO = "introducao"
_MAX_PALAVRAS = 300


class DocumentoInvalido(ValueError):
    pass


class _Frontmatter(BaseModel):
    model_config = ConfigDict(frozen=True)

    tipo: str
    data: date
    tags: list[str]


@dataclass(frozen=True)
class _Secao:
    caminho: tuple[str, ...]
    corpo: str


def ler_corpus(pasta: Path) -> list[Trecho]:
    trechos: list[Trecho] = []
    for arquivo in sorted(pasta.rglob("*.md")):
        if arquivo.name == "README.md":
            continue
        documento = arquivo.relative_to(pasta).as_posix()
        trechos.extend(_ler_documento(documento, arquivo.read_text(encoding="utf-8")))
    return trechos


def _ler_documento(documento: str, conteudo: str) -> list[Trecho]:
    meta, corpo = _frontmatter(documento, conteudo)
    titulos_documento, secoes = _secoes(corpo)
    if len(titulos_documento) != 1:
        raise DocumentoInvalido(f"{documento}: precisa de exatamente um título '# '")
    [titulo_documento] = titulos_documento
    trechos = []
    usados: set[str] = set()
    for secao in secoes:
        titulo = " > ".join((titulo_documento, *secao.caminho))
        slug = _sem_colisao(_slug_caminho(secao.caminho), usados)
        partes = _partes(secao.corpo)
        for numero, parte in enumerate(partes, start=1):
            trechos.append(
                Trecho(
                    id=f"{documento}#{slug}~{numero}" if len(partes) > 1 else f"{documento}#{slug}",
                    documento=documento,
                    titulo=titulo,
                    tipo=meta.tipo,
                    data=meta.data,
                    tags=meta.tags,
                    texto=f"{titulo}\n\n{parte}",
                )
            )
    return trechos


def _frontmatter(documento: str, conteudo: str) -> tuple[_Frontmatter, str]:
    partes = _PADRAO_FRONTMATTER.match(conteudo)
    if partes is None:
        raise DocumentoInvalido(f"{documento}: sem frontmatter YAML")
    try:
        meta = _Frontmatter.model_validate(yaml.safe_load(partes.group(1)))
    except (yaml.YAMLError, ValueError) as erro:
        raise DocumentoInvalido(f"{documento}: frontmatter inválido: {erro}") from erro
    return meta, partes.group(2)


def _secoes(corpo: str) -> tuple[list[str], list[_Secao]]:
    titulos_documento: list[str] = []
    caminho: tuple[str, ...] = ()
    linhas: list[str] = []
    secoes: list[_Secao] = []

    def fechar() -> None:
        texto = "\n".join(linhas).strip()
        if texto:
            secoes.append(_Secao(caminho, texto))
        linhas.clear()

    for linha in corpo.splitlines():
        titulo = _PADRAO_TITULO.match(linha)
        if titulo is None:
            linhas.append(linha)
            continue
        fechar()
        nivel, texto = len(titulo.group(1)), titulo.group(2)
        if nivel == 1:
            titulos_documento.append(texto)
        elif nivel == 2:
            caminho = (texto,)
        else:
            caminho = (*caminho[:1], texto)
    fechar()
    return titulos_documento, secoes


def _partes(corpo: str) -> list[str]:
    if len(corpo.split()) <= _MAX_PALAVRAS:
        return [corpo]
    partes: list[list[str]] = [[]]
    palavras_na_parte = 0
    for paragrafo in re.split(r"\n\s*\n", corpo):
        palavras = len(paragrafo.split())
        if partes[-1] and palavras_na_parte + palavras > _MAX_PALAVRAS:
            partes.append([])
            palavras_na_parte = 0
        partes[-1].append(paragrafo)
        palavras_na_parte += palavras
    return ["\n\n".join(parte) for parte in partes]


def _sem_colisao(slug: str, usados: set[str]) -> str:
    candidato, n = slug, 1
    while candidato in usados:
        n += 1
        candidato = f"{slug}-{n}"
    usados.add(candidato)
    return candidato


def _slug_caminho(caminho: tuple[str, ...]) -> str:
    if not caminho:
        return _SLUG_INTRODUCAO
    return "/".join(_slug(titulo) for titulo in caminho)


def _slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")
