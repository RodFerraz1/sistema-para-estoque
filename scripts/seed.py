"""Seed reprodutível do ERP fake.

Executa via: uv run python -m scripts.seed

Idempotente: apaga tudo do schema `erp` e repopula. Chamar duas vezes seguidas
deixa o banco no mesmo estado (mesmos UUIDs, mesmas quantidades) graças à
semente fixa em `random.Random(SEED)` e a UUIDs determinísticos via `uuid5`.
"""
from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.db.engine import get_engine

SEED = 42
NOW = datetime(2026, 9, 1, tzinfo=UTC)
PRECO_SOBE_POR_MES = 0.01
HISTORY_MONTHS = 24
HISTORY_START = NOW - timedelta(days=HISTORY_MONTHS * 30)


@dataclass(frozen=True)
class ProdutoSpec:
    nome: str
    categoria: str
    cores: tuple[str, ...]
    tamanhos: tuple[str, ...]
    gramaturas: tuple[int | None, ...]
    material: str


PRODUTOS: tuple[ProdutoSpec, ...] = (
    ProdutoSpec(
        "Toalha Banho Conforto", "felpudo",
        ("bege", "branco", "cinza", "azul"),
        ("70x140",), (400, 450), "algodão 100%",
    ),
    ProdutoSpec(
        "Toalha Banho Premium", "felpudo",
        ("branco", "grafite", "vinho", "azul-marinho"),
        ("80x150",), (500, 550), "algodão 100% penteado",
    ),
    ProdutoSpec(
        "Toalha Rosto Conforto", "felpudo",
        ("bege", "branco", "cinza", "verde"),
        ("48x80",), (380,), "algodão 100%",
    ),
    ProdutoSpec(
        "Toalha Piso Antiderrapante", "felpudo",
        ("bege", "azul", "vinho"),
        ("50x70",), (700,), "algodão + poliéster",
    ),
    ProdutoSpec(
        "Jogo de Cama Percal 200 fios", "jogo_cama",
        ("branco", "bege", "cinza", "rosa"),
        ("solteiro", "casal", "queen"),
        (None,), "percal 200 fios",
    ),
    ProdutoSpec(
        "Jogo de Cama Percal 300 fios", "jogo_cama",
        ("branco", "champagne"),
        ("casal", "queen", "king"),
        (None,), "percal 300 fios",
    ),
    ProdutoSpec(
        "Edredom Duplaface", "jogo_cama",
        ("bege/marrom", "cinza/branco"),
        ("casal", "queen"),
        (None,), "microfibra",
    ),
    ProdutoSpec(
        "Colcha Bouti", "jogo_cama",
        ("bege", "azul", "off-white"),
        ("solteiro", "casal", "queen"),
        (None,), "poliéster",
    ),
    ProdutoSpec(
        "Toalha de Mesa Retangular", "mesa",
        ("branco", "off-white", "azul", "vermelho"),
        ("140x220", "160x270"),
        (None,), "algodão + poliéster",
    ),
    ProdutoSpec(
        "Toalha de Mesa Redonda", "mesa",
        ("branco", "bege", "verde"),
        ("d160",),
        (None,), "algodão",
    ),
    ProdutoSpec(
        "Jogo Americano", "mesa",
        ("bege", "cinza", "azul"),
        ("35x50",),
        (None,), "juta",
    ),
    ProdutoSpec(
        "Guardanapo Tecido", "mesa",
        ("branco", "bege", "verde"),
        ("40x40",),
        (None,), "algodão",
    ),
    ProdutoSpec(
        "Pano de Prato Estampado", "cozinha",
        ("estampa1", "estampa2", "estampa3"),
        ("45x65",),
        (None,), "algodão",
    ),
    ProdutoSpec(
        "Pano Multiuso", "cozinha",
        ("amarelo", "azul", "verde"),
        ("30x40",),
        (None,), "não-tecido",
    ),
    ProdutoSpec(
        "Luva Térmica", "cozinha",
        ("vermelho", "preto", "azul"),
        ("único",),
        (None,), "algodão + silicone",
    ),
)


@dataclass(frozen=True)
class FornecedorSpec:
    nome: str
    cnpj: str
    prazo_pagamento: str
    pedido_minimo: int
    lead_time: int


FORNECEDORES: tuple[FornecedorSpec, ...] = (
    FornecedorSpec("Katrina Têxtil", "12.345.678/0001-90", "30/60/90", 12_000, 35),
    FornecedorSpec("Verdela Home", "23.456.789/0001-12", "28/56", 25_000, 60),
    FornecedorSpec("Malha Fina", "34.567.890/0001-45", "21/42", 8_000, 25),
    FornecedorSpec("Aurora Home Center", "45.678.901/0001-11", "30/60", 10_000, 40),
    FornecedorSpec("Riva Têxtil", "56.789.012/0001-22", "30/45", 6_000, 20),
)


CATEGORIA_FORNECEDORES: dict[str, tuple[int, ...]] = {
    "felpudo": (0, 3, 4),
    "jogo_cama": (0, 1, 3),
    "mesa": (2, 3, 4),
    "cozinha": (2, 3, 4),
}

MESES_SAZONALIDADE: dict[int, float] = {
    1: 0.85,
    2: 0.70,
    3: 0.75,
    4: 0.95,
    5: 1.25,
    6: 1.05,
    7: 1.00,
    8: 1.05,
    9: 1.10,
    10: 1.15,
    11: 1.60,
    12: 1.75,
}


_UUID_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000000")


def _uuid(namespace: str, key: str) -> uuid.UUID:
    return uuid.uuid5(_UUID_NAMESPACE, f"{namespace}:{key}")


def _sku_code(produto_nome: str, cor: str, tamanho: str, idx: int) -> str:
    parts = "".join(w[0] for w in produto_nome.split() if w).upper()[:4]
    cor_slug = cor.replace(" ", "").replace("/", "")[:4].upper()
    tam_slug = tamanho.replace("x", "").replace(" ", "").upper()
    return f"{parts}-{cor_slug}-{tam_slug}-{idx:02d}"


def _giro_alvo(rng: random.Random, categoria: str) -> float:
    base = {
        "felpudo": (40, 180),
        "jogo_cama": (15, 80),
        "mesa": (25, 120),
        "cozinha": (60, 250),
    }[categoria]
    return rng.uniform(*base)


def _wipe(conn: Connection) -> None:
    for table in (
        "pedidos_compra_itens",
        "pedidos_compra",
        "vendas",
        "movimentacoes_estoque",
        "estoque_snapshot",
        "fornecedores_skus",
        "skus",
        "produtos",
        "fornecedores",
    ):
        conn.execute(text(f"TRUNCATE erp.{table} CASCADE"))


def _seed_produtos_e_skus(conn: Connection) -> list[dict]:
    produtos_rows = []
    skus_rows = []
    skus_por_id: list[dict] = []

    for spec in PRODUTOS:
        produto_id = _uuid("produto", spec.nome)
        produtos_rows.append(
            {
                "id": produto_id,
                "nome": spec.nome,
                "categoria": spec.categoria,
                "descricao": f"{spec.nome} - {spec.material}",
                "ativo": True,
                "criado_em": HISTORY_START,
            }
        )
        idx = 0
        for cor in spec.cores:
            for tamanho in spec.tamanhos:
                for gramatura in spec.gramaturas:
                    idx += 1
                    sku_id = _uuid("sku", f"{spec.nome}|{cor}|{tamanho}|{gramatura}")
                    code = _sku_code(spec.nome, cor, tamanho, idx)
                    sku_row = {
                        "id": sku_id,
                        "produto_id": produto_id,
                        "sku_code": code,
                        "cor": cor,
                        "tamanho": tamanho,
                        "gramatura": gramatura,
                        "material": spec.material,
                        "ativo": True,
                        "criado_em": HISTORY_START,
                    }
                    skus_rows.append(sku_row)
                    skus_por_id.append(
                        {
                            **sku_row,
                            "categoria": spec.categoria,
                            "produto_nome": spec.nome,
                        }
                    )

    conn.execute(
        text(
            """
            INSERT INTO erp.produtos (id, nome, categoria, descricao, ativo, criado_em)
            VALUES (:id, :nome, :categoria, :descricao, :ativo, :criado_em)
            """
        ),
        produtos_rows,
    )
    conn.execute(
        text(
            """
            INSERT INTO erp.skus (id, produto_id, sku_code, cor, tamanho, gramatura, material, ativo, criado_em)
            VALUES (:id, :produto_id, :sku_code, :cor, :tamanho, :gramatura, :material, :ativo, :criado_em)
            """
        ),
        skus_rows,
    )
    return skus_por_id


def _seed_fornecedores(conn: Connection) -> list[dict]:
    rows = []
    for spec in FORNECEDORES:
        rows.append(
            {
                "id": _uuid("fornecedor", spec.nome),
                "nome": spec.nome,
                "cnpj": spec.cnpj,
                "prazo_pagamento_padrao": spec.prazo_pagamento,
                "pedido_minimo_reais": spec.pedido_minimo,
                "lead_time_dias_contratado": spec.lead_time,
                "ativo": True,
                "criado_em": HISTORY_START,
            }
        )
    conn.execute(
        text(
            """
            INSERT INTO erp.fornecedores
              (id, nome, cnpj, prazo_pagamento_padrao, pedido_minimo_reais,
               lead_time_dias_contratado, ativo, criado_em)
            VALUES
              (:id, :nome, :cnpj, :prazo_pagamento_padrao, :pedido_minimo_reais,
               :lead_time_dias_contratado, :ativo, :criado_em)
            """
        ),
        rows,
    )
    return rows


def _seed_fornecedor_skus(
    conn: Connection,
    rng: random.Random,
    fornecedores: list[dict],
    skus: list[dict],
) -> list[dict]:
    relacoes = []
    seen: set[tuple[uuid.UUID, uuid.UUID]] = set()
    for sku in skus:
        candidatos_idx = CATEGORIA_FORNECEDORES[sku["categoria"]]
        n = rng.randint(2, min(3, len(candidatos_idx)))
        escolhidos = rng.sample(candidatos_idx, k=n)
        for forn_idx in escolhidos:
            fornecedor = fornecedores[forn_idx]
            key = (fornecedor["id"], sku["id"])
            if key in seen:
                continue
            seen.add(key)
            preco_base = {
                "felpudo": 1800,
                "jogo_cama": 8500,
                "mesa": 2400,
                "cozinha": 600,
            }[sku["categoria"]]
            preco = int(preco_base * rng.uniform(0.85, 1.25))
            relacoes.append(
                {
                    "fornecedor_id": fornecedor["id"],
                    "sku_id": sku["id"],
                    "preco_unitario_atual": preco,
                    "moq_unidades": rng.choice((24, 36, 48, 60, 120)),
                    "lead_time_dias_observado": max(
                        1,
                        fornecedor["lead_time_dias_contratado"]
                        + rng.randint(-5, 12),
                    ),
                    "ativo": True,
                    "atualizado_em": NOW,
                }
            )
    conn.execute(
        text(
            """
            INSERT INTO erp.fornecedores_skus
              (fornecedor_id, sku_id, preco_unitario_atual, moq_unidades,
               lead_time_dias_observado, ativo, atualizado_em)
            VALUES
              (:fornecedor_id, :sku_id, :preco_unitario_atual, :moq_unidades,
               :lead_time_dias_observado, :ativo, :atualizado_em)
            """
        ),
        relacoes,
    )
    return relacoes


def _seed_historico(
    conn: Connection,
    rng: random.Random,
    skus: list[dict],
    relacoes: list[dict],
) -> None:
    vendas_rows: list[dict] = []
    movimentacoes_rows: list[dict] = []
    snapshot_rows: list[dict] = []

    relacoes_por_sku: dict[uuid.UUID, list[dict]] = {}
    for rel in relacoes:
        relacoes_por_sku.setdefault(rel["sku_id"], []).append(rel)

    for sku in skus:
        giro_mensal = _giro_alvo(rng, sku["categoria"])
        preco_venda_unit = int(
            relacoes_por_sku[sku["id"]][0]["preco_unitario_atual"]
            * rng.uniform(1.35, 1.75)
        )

        estoque = int(giro_mensal * rng.uniform(1.5, 3.0))
        movimentacoes_rows.append(
            {
                "id": _uuid("mov_init", str(sku["id"])),
                "sku_id": sku["id"],
                "tipo": "entrada_compra",
                "quantidade": estoque,
                "data": HISTORY_START,
                "referencia_tipo": "ajuste_manual",
                "referencia_id": None,
                "observacao": "Saldo inicial de seed",
            }
        )

        for mes_offset in range(HISTORY_MONTHS):
            data_mes = HISTORY_START + timedelta(days=mes_offset * 30)
            fator = MESES_SAZONALIDADE[data_mes.month]
            demanda_mes = max(1, int(giro_mensal * fator * rng.uniform(0.85, 1.15)))

            vendas_do_mes = rng.randint(4, 12)
            pesos = [rng.uniform(0.6, 1.4) for _ in range(vendas_do_mes)]
            total_peso = sum(pesos)
            quantidades = [max(1, int(demanda_mes * p / total_peso)) for p in pesos]

            for v_idx, qtd in enumerate(quantidades):
                if qtd > estoque:
                    reposicao = int(giro_mensal * rng.uniform(1.0, 2.0))
                    movimentacoes_rows.append(
                        {
                            "id": _uuid(
                                "mov_repo",
                                f"{sku['id']}|{mes_offset}|{v_idx}",
                            ),
                            "sku_id": sku["id"],
                            "tipo": "entrada_compra",
                            "quantidade": reposicao,
                            "data": data_mes + timedelta(days=v_idx),
                            "referencia_tipo": "pedido_compra",
                            "referencia_id": None,
                            "observacao": "Reposição sazonal",
                        }
                    )
                    estoque += reposicao

                dia = rng.randint(0, 27)
                data_venda = data_mes + timedelta(days=dia, hours=rng.randint(8, 18))
                venda_id = _uuid("venda", f"{sku['id']}|{mes_offset}|{v_idx}")
                vendas_rows.append(
                    {
                        "id": venda_id,
                        "sku_id": sku["id"],
                        "quantidade": qtd,
                        "valor_unitario_reais": preco_venda_unit,
                        "data": data_venda,
                        "cliente_ref": f"varejista-{rng.randint(1, 40):03d}",
                    }
                )
                movimentacoes_rows.append(
                    {
                        "id": _uuid("mov_venda", str(venda_id)),
                        "sku_id": sku["id"],
                        "tipo": "saida_venda",
                        "quantidade": qtd,
                        "data": data_venda,
                        "referencia_tipo": "venda",
                        "referencia_id": venda_id,
                        "observacao": None,
                    }
                )
                estoque -= qtd

            if mes_offset in (5, 11, 17) and rng.random() < 0.4:
                ajuste = rng.randint(1, 3)
                movimentacoes_rows.append(
                    {
                        "id": _uuid("mov_aj", f"{sku['id']}|{mes_offset}"),
                        "sku_id": sku["id"],
                        "tipo": "ajuste_negativo",
                        "quantidade": ajuste,
                        "data": data_mes + timedelta(days=28),
                        "referencia_tipo": "ajuste_manual",
                        "referencia_id": None,
                        "observacao": "Perda de inventário",
                    }
                )
                estoque -= ajuste

        # Target coverage entre 0.5 e 4 meses.
        coverage_alvo = rng.uniform(0.5, 4.0)
        alvo = max(1, int(giro_mensal * coverage_alvo))
        delta = alvo - estoque
        if delta > 0:
            movimentacoes_rows.append(
                {
                    "id": _uuid("mov_final_pos", str(sku["id"])),
                    "sku_id": sku["id"],
                    "tipo": "entrada_compra",
                    "quantidade": delta,
                    "data": NOW - timedelta(days=7),
                    "referencia_tipo": "pedido_compra",
                    "referencia_id": None,
                    "observacao": "Recebimento recente",
                }
            )
            estoque += delta
        elif delta < 0:
            movimentacoes_rows.append(
                {
                    "id": _uuid("mov_final_neg", str(sku["id"])),
                    "sku_id": sku["id"],
                    "tipo": "ajuste_negativo",
                    "quantidade": -delta,
                    "data": NOW - timedelta(days=3),
                    "referencia_tipo": "ajuste_manual",
                    "referencia_id": None,
                    "observacao": "Ajuste de cobertura",
                }
            )
            estoque += delta

        reservada = max(0, int(estoque * rng.uniform(0.0, 0.15)))
        snapshot_rows.append(
            {
                "sku_id": sku["id"],
                "quantidade_disponivel": max(0, estoque - reservada),
                "quantidade_reservada": reservada,
                "atualizado_em": NOW,
            }
        )

    _bulk_insert(
        conn,
        """
        INSERT INTO erp.vendas
          (id, sku_id, quantidade, valor_unitario_reais, data, cliente_ref)
        VALUES
          (:id, :sku_id, :quantidade, :valor_unitario_reais, :data, :cliente_ref)
        """,
        vendas_rows,
    )
    _bulk_insert(
        conn,
        """
        INSERT INTO erp.movimentacoes_estoque
          (id, sku_id, tipo, quantidade, data, referencia_tipo, referencia_id, observacao)
        VALUES
          (:id, :sku_id, :tipo, :quantidade, :data, :referencia_tipo, :referencia_id, :observacao)
        """,
        movimentacoes_rows,
    )
    _bulk_insert(
        conn,
        """
        INSERT INTO erp.estoque_snapshot
          (sku_id, quantidade_disponivel, quantidade_reservada, atualizado_em)
        VALUES
          (:sku_id, :quantidade_disponivel, :quantidade_reservada, :atualizado_em)
        """,
        snapshot_rows,
    )


def _seed_pedidos_compra(
    conn: Connection,
    rng: random.Random,
    fornecedores: list[dict],
    relacoes: list[dict],
) -> None:
    status_dist = [
        ("recebido_total", 6),
        ("recebido_parcial", 2),
        ("enviado", 3),
        ("aprovado", 2),
        ("rascunho", 1),
        ("cancelado", 1),
    ]
    ordered_status: list[str] = []
    for status, count in status_dist:
        ordered_status.extend([status] * count)

    rel_por_fornecedor: dict[uuid.UUID, list[dict]] = {}
    for rel in relacoes:
        rel_por_fornecedor.setdefault(rel["fornecedor_id"], []).append(rel)

    pedidos_rows: list[dict] = []
    itens_rows: list[dict] = []

    for idx, status in enumerate(ordered_status):
        fornecedor = fornecedores[idx % len(fornecedores)]
        rels = rel_por_fornecedor[fornecedor["id"]]
        criado_em = NOW - timedelta(days=180 - idx * 10)
        aprovado_em = criado_em + timedelta(days=2) if status != "rascunho" else None
        enviado_em = (
            aprovado_em + timedelta(days=1)
            if status in ("enviado", "recebido_parcial", "recebido_total")
            and aprovado_em is not None
            else None
        )
        recebido_em = (
            enviado_em + timedelta(days=fornecedor["lead_time_dias_contratado"])
            if status in ("recebido_parcial", "recebido_total") and enviado_em is not None
            else None
        )
        data_prevista = (
            (enviado_em + timedelta(days=fornecedor["lead_time_dias_contratado"])).date()
            if enviado_em is not None
            else None
        )

        pedido_id = _uuid("pedido", f"{idx}|{status}")
        n_itens = rng.randint(3, 6)
        item_rels = rng.sample(rels, k=min(n_itens, len(rels)))
        valor_total = 0
        for item_idx, rel in enumerate(item_rels):
            qtd = rel["moq_unidades"] * rng.randint(1, 3)
            # Pedido mais antigo saiu mais barato (1% por mês até hoje), para o histórico
            # de preço ter o que mostrar na negociação com o representante.
            meses_atras = (NOW - criado_em).days / 30
            preco = round(rel["preco_unitario_atual"] * (1 - PRECO_SOBE_POR_MES * meses_atras))
            quantidade_recebida = 0
            if status == "recebido_total":
                quantidade_recebida = qtd
            elif status == "recebido_parcial":
                quantidade_recebida = max(1, int(qtd * rng.uniform(0.3, 0.7)))
            itens_rows.append(
                {
                    "id": _uuid("pedido_item", f"{pedido_id}|{item_idx}"),
                    "pedido_id": pedido_id,
                    "sku_id": rel["sku_id"],
                    "quantidade": qtd,
                    "preco_unitario_reais": preco,
                    "quantidade_recebida": quantidade_recebida,
                }
            )
            valor_total += qtd * preco

        pedidos_rows.append(
            {
                "id": pedido_id,
                "fornecedor_id": fornecedor["id"],
                "status": status,
                "criado_em": criado_em,
                "aprovado_em": aprovado_em,
                "enviado_em": enviado_em,
                "recebido_em": recebido_em,
                "data_prevista_entrega": data_prevista,
                "valor_total_reais": valor_total,
                "observacao": None,
            }
        )

    conn.execute(
        text(
            """
            INSERT INTO erp.pedidos_compra
              (id, fornecedor_id, status, criado_em, aprovado_em, enviado_em,
               recebido_em, data_prevista_entrega, valor_total_reais, observacao)
            VALUES
              (:id, :fornecedor_id, :status, :criado_em, :aprovado_em, :enviado_em,
               :recebido_em, :data_prevista_entrega, :valor_total_reais, :observacao)
            """
        ),
        pedidos_rows,
    )
    conn.execute(
        text(
            """
            INSERT INTO erp.pedidos_compra_itens
              (id, pedido_id, sku_id, quantidade, preco_unitario_reais, quantidade_recebida)
            VALUES
              (:id, :pedido_id, :sku_id, :quantidade, :preco_unitario_reais, :quantidade_recebida)
            """
        ),
        itens_rows,
    )


def _bulk_insert(conn: Connection, sql: str, rows: Iterable[dict], chunk: int = 500) -> None:
    buffer: list[dict] = []
    stmt = text(sql)
    for row in rows:
        buffer.append(row)
        if len(buffer) >= chunk:
            conn.execute(stmt, buffer)
            buffer.clear()
    if buffer:
        conn.execute(stmt, buffer)


def run() -> None:
    rng = random.Random(SEED)
    engine = get_engine()
    with engine.begin() as conn:
        _wipe(conn)
        skus = _seed_produtos_e_skus(conn)
        fornecedores = _seed_fornecedores(conn)
        relacoes = _seed_fornecedor_skus(conn, rng, fornecedores, skus)
        _seed_historico(conn, rng, skus, relacoes)
        _seed_pedidos_compra(conn, rng, fornecedores, relacoes)


if __name__ == "__main__":
    run()
