"""Fábricas de DTOs de domínio para montar os adapters em memória nos testes.

Mantém defaults sensatos para que cada teste especifique apenas o que
importa. UUIDs são derivados por `uuid5` a partir do nome/código para
serem estáveis entre runs.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from src.ai.embeddings import Embedder
from src.ai.in_memory import InMemoryTrechosRepositorio
from src.ai.redator import Redator, RedatorIndisponivel
from src.ai.schemas import NENHUM_PRODUTO, Entendimento, Escolha, Intencao, Relacao, Trecho, TrechoIndexado
from src.catalog.schemas import SKU, Fornecedor, FornecedorParaSKU
from src.erp_adapter.in_memory import ItemPedidoCompra, PedidoCompra
from src.erp_adapter.schemas import StatusPedidoCompra
from src.inventory.schemas import Estoque, Movimentacao
from src.sales.schemas import Venda
from src.usuarios.schemas import Papel, Usuario


_NS = uuid.UUID("00000000-0000-0000-0000-000000000fff")


def uid(kind: str, key: str) -> UUID:
    return uuid.uuid5(_NS, f"{kind}:{key}")


def make_sku(
    sku_code: str = "TESTE-001",
    *,
    produto_nome: str = "Produto Teste",
    categoria: str = "felpudo",
    cor: str = "branco",
    tamanho: str = "70x140",
    gramatura: int | None = 400,
    material: str | None = "algodão 100%",
    ativo: bool = True,
) -> SKU:
    return SKU(
        id=uid("sku", sku_code),
        produto_id=uid("produto", produto_nome),
        sku_code=sku_code,
        produto_nome=produto_nome,
        categoria=categoria,
        cor=cor,
        tamanho=tamanho,
        gramatura=gramatura,
        material=material,
        ativo=ativo,
    )


def make_fornecedor(
    nome: str = "Katrina Têxtil",
    *,
    lead_time_dias_contratado: int = 30,
    pedido_minimo_reais: int = 10_000,
    ativo: bool = True,
) -> Fornecedor:
    return Fornecedor(
        id=uid("fornecedor", nome),
        nome=nome,
        cnpj="00.000.000/0001-00",
        prazo_pagamento_padrao="30/60",
        pedido_minimo_reais=pedido_minimo_reais,
        lead_time_dias_contratado=lead_time_dias_contratado,
        ativo=ativo,
    )


def make_fornecedor_sku(
    fornecedor: Fornecedor,
    *,
    preco_unitario_reais: int = 2000,
    moq_unidades: int = 48,
    lead_time_dias_observado: int | None = 35,
) -> FornecedorParaSKU:
    return FornecedorParaSKU(
        fornecedor_id=fornecedor.id,
        fornecedor_nome=fornecedor.nome,
        preco_unitario_reais=preco_unitario_reais,
        moq_unidades=moq_unidades,
        lead_time_dias_contratado=fornecedor.lead_time_dias_contratado,
        lead_time_dias_observado=lead_time_dias_observado,
        prazo_pagamento_padrao=fornecedor.prazo_pagamento_padrao,
        pedido_minimo_reais=fornecedor.pedido_minimo_reais,
    )


def make_estoque(
    *,
    disponivel: int = 100,
    reservada: int = 0,
    atualizado_em: datetime | None = None,
) -> Estoque:
    return Estoque(
        quantidade_disponivel=disponivel,
        quantidade_reservada=reservada,
        atualizado_em=atualizado_em or datetime(2026, 9, 1, tzinfo=UTC),
    )


def make_venda(
    sku: SKU,
    data: datetime,
    quantidade: int,
    *,
    key: str | None = None,
    valor_unitario_reais: int = 3000,
    cliente_ref: str = "varejista-001",
) -> Venda:
    ref = key or f"{sku.sku_code}|{data.isoformat()}|{quantidade}"
    return Venda(
        id=uid("venda", ref),
        sku_id=sku.id,
        quantidade=quantidade,
        valor_unitario_reais=valor_unitario_reais,
        data=data,
        cliente_ref=cliente_ref,
    )


def make_movimentacao(
    sku: SKU,
    data: datetime,
    tipo: str,
    quantidade: int,
    *,
    key: str | None = None,
) -> Movimentacao:
    ref = key or f"{sku.sku_code}|{tipo}|{data.isoformat()}|{quantidade}"
    return Movimentacao(
        id=uid("mov", ref),
        sku_id=sku.id,
        tipo=tipo,
        quantidade=quantidade,
        data=data,
        referencia_tipo=None,
        referencia_id=None,
        observacao=None,
    )


def make_pedido_compra(
    fornecedor: Fornecedor,
    status: StatusPedidoCompra,
    *,
    key: str | None = None,
    data_prevista_entrega: date | None = None,
    criado_em: datetime | None = None,
) -> PedidoCompra:
    return PedidoCompra(
        id=uid("pedido", key or f"{fornecedor.nome}|{status}"),
        fornecedor_id=fornecedor.id,
        status=status,
        data_prevista_entrega=data_prevista_entrega,
        criado_em=criado_em or datetime(2026, 6, 1, tzinfo=UTC),
    )


def make_item_pedido_compra(
    pedido: PedidoCompra,
    sku: SKU,
    *,
    quantidade: int,
    quantidade_recebida: int = 0,
    preco_unitario_centavos: int = 0,
) -> ItemPedidoCompra:
    return ItemPedidoCompra(
        pedido_id=pedido.id,
        sku_id=sku.id,
        quantidade=quantidade,
        quantidade_recebida=quantidade_recebida,
        preco_unitario_centavos=preco_unitario_centavos,
    )


def make_trecho(
    id: str,
    texto: str = "Texto do trecho.",
    *,
    titulo: str = "Documento > Seção",
    tipo: str = "reuniao",
    data: date = date(2025, 3, 14),
    tags: list[str] | None = None,
) -> Trecho:
    return Trecho(
        id=id,
        documento=id.split("#")[0],
        titulo=titulo,
        tipo=tipo,
        data=data,
        tags=tags or [],
        texto=texto,
    )


def repositorio_com(trechos: list[Trecho], embedder: Embedder) -> InMemoryTrechosRepositorio:
    """Grava os `trechos` já com embedding, agrupados por documento como na ingestão."""
    repositorio = InMemoryTrechosRepositorio()
    por_documento: dict[str, list[TrechoIndexado]] = defaultdict(list)
    for trecho, vetor in zip(trechos, embedder.embed([t.texto for t in trechos]), strict=True):
        por_documento[trecho.documento].append(TrechoIndexado(**trecho.model_dump(), embedding=vetor))
    for documento, indexados in por_documento.items():
        repositorio.substituir_documento(documento, f"hash de {documento}", indexados)
    return repositorio


def make_entendimento(
    intencao: Intencao = "situacao_sku",
    confianca: float = 0.95,
    *,
    produto: str = NENHUM_PRODUTO,
    confianca_produto: float = 0.95,
    probabilidades_intencao: dict[str, float] | None = None,
    probabilidades_produto: dict[str, float] | None = None,
    modelo: str = "in-memory",
) -> Entendimento:
    return Entendimento(
        intencao=Escolha(
            escolha=intencao,
            confianca=confianca,
            probabilidades=probabilidades_intencao or {intencao: confianca},
        ),
        produto=Escolha(
            escolha=produto,
            confianca=confianca_produto,
            probabilidades=probabilidades_produto or {produto: confianca_produto},
        ),
        modelo=modelo,
    )


def make_relacao(escolha: Relacao, confianca: float = 0.95) -> Escolha[Relacao]:
    """Resposta da pergunta de citação para configurar o `InMemoryDecisionModel`."""
    return Escolha(escolha=escolha, confianca=confianca, probabilidades={escolha: confianca})


class RedatorGravador(Redator):
    """Redator que guarda o que recebeu e devolve `texto`. Com `falhar`, lança
    `RedatorIndisponivel` como um LLM fora do ar."""

    usa_llm = True

    def __init__(self, texto: str = "Resposta redigida.", *, nome: str = "gravador", falhar: bool = False) -> None:
        self._nome = nome
        self.chamadas: list[tuple[str, str]] = []
        self._texto = texto
        self._falhar = falhar

    @property
    def nome(self) -> str:
        return self._nome

    def redigir(self, pergunta: str, contexto: str) -> str:
        self.chamadas.append((pergunta, contexto))
        if self._falhar:
            raise RedatorIndisponivel(f"{self.nome} configurado para falhar")
        return self._texto


class RelogioFake:
    """Relógio controlado pelo teste, para a hora dos avisos e das decisões de compra."""

    def __init__(self, agora: datetime) -> None:
        self.agora = agora

    def __call__(self) -> datetime:
        return self.agora

    def avancar(self, **duracao: float) -> None:
        self.agora += timedelta(**duracao)


def make_usuario(
    nome: str = "Pessoa Teste",
    *,
    papeis: list[Papel] | None = None,
    email: str | None = None,
) -> Usuario:
    return Usuario(
        id=uid("usuario", nome),
        nome=nome,
        email=email or f"{nome.lower().replace(' ', '.')}@loja.com",
        senha_hash="$argon2id$falso",
        papeis=papeis or ["comprador"],
        ativo=True,
        criado_em=datetime(2026, 10, 1, tzinfo=UTC),
        ultimo_acesso_em=None,
    )
