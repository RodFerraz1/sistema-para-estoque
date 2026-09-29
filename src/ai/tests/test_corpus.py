"""Testes de `ler_corpus` com markdown de fixture e com o `corpus/` real."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.ai.corpus import DocumentoInvalido, ler_corpus

CORPUS = Path(__file__).resolve().parents[3] / "corpus"

FRONTMATTER = """---
tipo: reuniao
data: 2025-03-14
tags: [fornecedores, sazonalidade]
---
"""


def escrever(pasta: Path, caminho: str, conteudo: str) -> None:
    arquivo = pasta / caminho
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(conteudo, encoding="utf-8")


def paragrafo(palavra: str, n: int) -> str:
    return " ".join([palavra] * n)


def test_secao_vira_trecho_com_metadados_do_frontmatter(tmp_path: Path) -> None:
    escrever(
        tmp_path,
        "reunioes/revisao.md",
        FRONTMATTER + "\n# Revisão Q1\n\n## Katrina Têxtil\n\nAtrasou 68 dias.\n",
    )

    [trecho] = ler_corpus(tmp_path)

    assert trecho.id == "reunioes/revisao.md#katrina-textil"
    assert trecho.documento == "reunioes/revisao.md"
    assert trecho.titulo == "Revisão Q1 > Katrina Têxtil"
    assert trecho.tipo == "reuniao"
    assert trecho.data == date(2025, 3, 14)
    assert trecho.tags == ["fornecedores", "sazonalidade"]
    assert trecho.texto == "Revisão Q1 > Katrina Têxtil\n\nAtrasou 68 dias."


def test_subsecao_usa_caminho_de_titulos_e_secao_so_com_titulo_nao_vira_trecho(
    tmp_path: Path,
) -> None:
    escrever(
        tmp_path,
        "contratos/katrina.md",
        FRONTMATTER
        + "\n# Contrato Katrina\n\n## Cláusulas comerciais\n\n### 3. Prazos\n\nAntecedência de 45 dias.\n",
    )

    [trecho] = ler_corpus(tmp_path)

    assert trecho.id == "contratos/katrina.md#clausulas-comerciais/3-prazos"
    assert trecho.titulo == "Contrato Katrina > Cláusulas comerciais > 3. Prazos"
    assert trecho.texto == "Contrato Katrina > Cláusulas comerciais > 3. Prazos\n\nAntecedência de 45 dias."


def test_texto_antes_do_primeiro_h2_vira_trecho_de_introducao(tmp_path: Path) -> None:
    escrever(
        tmp_path,
        "politica.md",
        FRONTMATTER + "\n# Política de estoque\n\nVersão: 3.\n\n## Regras\n\nTeto de 3 meses.\n",
    )

    introducao, regras = ler_corpus(tmp_path)

    assert introducao.id == "politica.md#introducao"
    assert introducao.titulo == "Política de estoque"
    assert introducao.texto == "Política de estoque\n\nVersão: 3."
    assert regras.id == "politica.md#regras"


def test_colisao_de_slug_ganha_sufixo(tmp_path: Path) -> None:
    escrever(
        tmp_path,
        "doc.md",
        FRONTMATTER + "\n# Doc\n\n## Riscos\n\nPrimeiro.\n\n## Riscos!\n\nSegundo.\n\n## Riscos?\n\nTerceiro.\n",
    )

    ids = [trecho.id for trecho in ler_corpus(tmp_path)]

    assert ids == ["doc.md#riscos", "doc.md#riscos-2", "doc.md#riscos-3"]


def test_secao_com_ate_300_palavras_nao_e_quebrada(tmp_path: Path) -> None:
    corpo = paragrafo("a", 150) + "\n\n" + paragrafo("b", 150)
    escrever(tmp_path, "doc.md", FRONTMATTER + f"\n# Doc\n\n## Longa\n\n{corpo}\n")

    [trecho] = ler_corpus(tmp_path)

    assert trecho.id == "doc.md#longa"


def test_secao_acima_de_300_palavras_e_quebrada_por_paragrafo(tmp_path: Path) -> None:
    corpo = "\n\n".join([paragrafo("a", 150), paragrafo("b", 150), paragrafo("c", 200)])
    escrever(tmp_path, "doc.md", FRONTMATTER + f"\n# Doc\n\n## Longa\n\n{corpo}\n")

    primeiro, segundo = ler_corpus(tmp_path)

    assert primeiro.id == "doc.md#longa~1"
    assert primeiro.titulo == "Doc > Longa"
    assert primeiro.texto == f"Doc > Longa\n\n{paragrafo('a', 150)}\n\n{paragrafo('b', 150)}"
    assert segundo.id == "doc.md#longa~2"
    assert segundo.texto == f"Doc > Longa\n\n{paragrafo('c', 200)}"


def test_readme_e_ignorado(tmp_path: Path) -> None:
    escrever(tmp_path, "README.md", "# Corpus\n\n## Estrutura\n\nSem frontmatter.\n")
    escrever(tmp_path, "politicas/README.md", "# Políticas\n\nSem frontmatter.\n")

    assert ler_corpus(tmp_path) == []


def test_documento_sem_frontmatter_falha_com_nome_do_arquivo(tmp_path: Path) -> None:
    escrever(tmp_path, "reunioes/sem-meta.md", "# Reunião\n\n## Pauta\n\nTexto.\n")

    with pytest.raises(DocumentoInvalido, match="reunioes/sem-meta.md"):
        ler_corpus(tmp_path)


@pytest.mark.parametrize("data", ["2025-13-40", "ontem"])
def test_documento_com_data_invalida_falha_com_nome_do_arquivo(tmp_path: Path, data: str) -> None:
    escrever(
        tmp_path,
        "reunioes/data-ruim.md",
        f"---\ntipo: reuniao\ndata: {data}\ntags: []\n---\n\n# Reunião\n\n## Pauta\n\nTexto.\n",
    )

    with pytest.raises(DocumentoInvalido, match="reunioes/data-ruim.md"):
        ler_corpus(tmp_path)


@pytest.mark.parametrize(
    "corpo",
    ["\n## Pauta\n\nTexto.\n", "\n# Reunião\n\n## Pauta\n\nTexto.\n\n# Outra\n\nMais.\n"],
    ids=["sem-titulo", "dois-titulos"],
)
def test_documento_sem_exatamente_um_titulo_falha_com_nome_do_arquivo(
    tmp_path: Path, corpo: str
) -> None:
    escrever(tmp_path, "reunioes/titulo.md", FRONTMATTER + corpo)

    with pytest.raises(DocumentoInvalido, match="reunioes/titulo.md"):
        ler_corpus(tmp_path)


def test_corpus_real_tem_ids_unicos_e_todo_documento_gera_trecho() -> None:
    trechos = ler_corpus(CORPUS)

    ids = [trecho.id for trecho in trechos]
    assert len(ids) == len(set(ids))
    documentos = {
        arquivo.relative_to(CORPUS).as_posix()
        for arquivo in CORPUS.rglob("*.md")
        if arquivo.name != "README.md"
    }
    assert documentos
    assert {trecho.documento for trecho in trechos} == documentos
