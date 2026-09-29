"""Testes de `ingerir` com `InMemoryTrechosRepositorio` e `FakeEmbedder`."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.ai.corpus import DocumentoInvalido
from src.ai.embeddings import DIMENSAO
from src.ai.in_memory import FakeEmbedder, InMemoryTrechosRepositorio
from src.ai.ingestao import ingerir

FRONTMATTER = "---\ntipo: reuniao\ndata: 2025-03-14\ntags: [fornecedores]\n---\n"


class EmbedderContador(FakeEmbedder):
    def __init__(self) -> None:
        self.textos_embedados: list[str] = []

    def embed(self, textos: list[str]) -> list[list[float]]:
        self.textos_embedados.extend(textos)
        return super().embed(textos)


def escrever(pasta: Path, caminho: str, secoes: dict[str, str]) -> None:
    corpo = "".join(f"## {titulo}\n\n{texto}\n\n" for titulo, texto in secoes.items())
    arquivo = pasta / caminho
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(f"{FRONTMATTER}\n# Documento\n\n{corpo}", encoding="utf-8")


def ids_indexados(repositorio: InMemoryTrechosRepositorio) -> set[str]:
    return {trecho.id for trecho in repositorio.buscar_similares([1.0] * DIMENSAO, k=1000)}


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    escrever(tmp_path, "fornecedores/katrina.md", {"Lead time": "Atrasa 68 dias.", "Preço": "Barato."})
    escrever(tmp_path, "politicas/estoque.md", {"Teto": "No máximo 3 meses de estoque."})
    return tmp_path


def test_primeira_ingestao_indexa_todos_os_documentos_como_novos(corpus: Path) -> None:
    repositorio = InMemoryTrechosRepositorio()

    relatorio = ingerir(corpus, FakeEmbedder(), repositorio)

    assert relatorio.novos == ["fornecedores/katrina.md", "politicas/estoque.md"]
    assert relatorio.alterados == relatorio.removidos == relatorio.inalterados == []
    assert relatorio.total_trechos == 3
    assert ids_indexados(repositorio) == {
        "fornecedores/katrina.md#lead-time",
        "fornecedores/katrina.md#preco",
        "politicas/estoque.md#teto",
    }
    assert set(repositorio.hashes_por_documento()) == {
        "fornecedores/katrina.md",
        "politicas/estoque.md",
    }


def test_trecho_indexado_e_encontrado_pelo_embedding_do_texto(corpus: Path) -> None:
    embedder = FakeEmbedder()
    repositorio = InMemoryTrechosRepositorio()
    ingerir(corpus, embedder, repositorio)

    [vetor] = embedder.embed(["Documento > Teto\n\nNo máximo 3 meses de estoque."])
    [mais_parecido] = repositorio.buscar_similares(vetor, k=1)

    assert mais_parecido.id == "politicas/estoque.md#teto"
    assert mais_parecido.similaridade == pytest.approx(1.0)


def test_segunda_ingestao_sem_mudanca_nao_regrava_nem_embeda(corpus: Path) -> None:
    repositorio = InMemoryTrechosRepositorio()
    ingerir(corpus, FakeEmbedder(), repositorio)
    hashes = repositorio.hashes_por_documento()
    embedder = EmbedderContador()

    relatorio = ingerir(corpus, embedder, repositorio)

    assert relatorio.inalterados == ["fornecedores/katrina.md", "politicas/estoque.md"]
    assert relatorio.novos == relatorio.alterados == relatorio.removidos == []
    assert relatorio.total_trechos == 3
    assert embedder.textos_embedados == []
    assert repositorio.hashes_por_documento() == hashes


def test_documento_alterado_tem_todos_os_trechos_substituidos(corpus: Path) -> None:
    repositorio = InMemoryTrechosRepositorio()
    ingerir(corpus, FakeEmbedder(), repositorio)
    escrever(corpus, "fornecedores/katrina.md", {"Lead time": "Agora atrasa 30 dias."})
    embedder = EmbedderContador()

    relatorio = ingerir(corpus, embedder, repositorio)

    assert relatorio.alterados == ["fornecedores/katrina.md"]
    assert relatorio.inalterados == ["politicas/estoque.md"]
    assert relatorio.total_trechos == 2
    assert ids_indexados(repositorio) == {
        "fornecedores/katrina.md#lead-time",
        "politicas/estoque.md#teto",
    }
    assert embedder.textos_embedados == ["Documento > Lead time\n\nAgora atrasa 30 dias."]


def test_documento_que_sumiu_da_pasta_tem_os_trechos_removidos(corpus: Path) -> None:
    repositorio = InMemoryTrechosRepositorio()
    ingerir(corpus, FakeEmbedder(), repositorio)
    (corpus / "fornecedores/katrina.md").unlink()

    relatorio = ingerir(corpus, FakeEmbedder(), repositorio)

    assert relatorio.removidos == ["fornecedores/katrina.md"]
    assert relatorio.inalterados == ["politicas/estoque.md"]
    assert relatorio.total_trechos == 1
    assert ids_indexados(repositorio) == {"politicas/estoque.md#teto"}
    assert set(repositorio.hashes_por_documento()) == {"politicas/estoque.md"}


def test_documento_invalido_aborta_antes_de_gravar_qualquer_coisa(corpus: Path) -> None:
    repositorio = InMemoryTrechosRepositorio()
    ingerir(corpus, FakeEmbedder(), repositorio)
    escrever(corpus, "politicas/estoque.md", {"Teto": "Agora 4 meses."})
    (corpus / "reunioes").mkdir()
    (corpus / "reunioes/sem-frontmatter.md").write_text("# Reunião\n\n## Pauta\n\nTexto.\n")
    antes = repositorio.hashes_por_documento()

    with pytest.raises(DocumentoInvalido):
        ingerir(corpus, FakeEmbedder(), repositorio)

    assert repositorio.hashes_por_documento() == antes


def test_documento_sem_trechos_nao_e_indexado_nem_reaparece_como_novo(corpus: Path) -> None:
    (corpus / "politicas/vazio.md").write_text(f"{FRONTMATTER}\n# Só o título\n")
    repositorio = InMemoryTrechosRepositorio()
    ingerir(corpus, FakeEmbedder(), repositorio)

    relatorio = ingerir(corpus, FakeEmbedder(), repositorio)

    assert relatorio.novos == []
    assert "politicas/vazio.md" not in relatorio.inalterados
    assert "politicas/vazio.md" not in repositorio.hashes_por_documento()


def test_documento_que_ficou_sem_trechos_e_removido(corpus: Path) -> None:
    repositorio = InMemoryTrechosRepositorio()
    ingerir(corpus, FakeEmbedder(), repositorio)
    (corpus / "politicas/estoque.md").write_text(f"{FRONTMATTER}\n# Só o título\n")

    relatorio = ingerir(corpus, FakeEmbedder(), repositorio)

    assert relatorio.removidos == ["politicas/estoque.md"]
    assert ids_indexados(repositorio) == {
        "fornecedores/katrina.md#lead-time",
        "fornecedores/katrina.md#preco",
    }
