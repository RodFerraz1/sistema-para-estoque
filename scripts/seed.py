"""Seed reprodutível do ERP fake.

Executa via: uv run python -m scripts.seed [--skus N]

`NOW` é o dia em que o seed roda (meia-noite UTC), com 24 meses de histórico para trás:
o padrão mensal até 90 dias atrás e, daí até ontem, no máximo uma venda por SKU e dia
aberto, com os domingos fechados. Hoje não tem venda.

Idempotente: apaga tudo do schema `erp` e repopula. Mesmo dia, mesmo banco: cada SKU tem
a própria semente (`random.Random` com a semente fixa e o código do SKU) e os UUIDs são
determinísticos via `uuid5`.

Cenários fixos da demonstração (códigos estáveis):
- `TAP-MARR-4060-01`, tapete marrom: vendia uns 10 por dia, vendeu 5 e depois 0 nos dois
  últimos dias abertos e tem estoque alto. Queda de venda com estoque.
- `TAP-*-4060-*`, as 5 cores do Tapete Banheiro: o marrom faz perto de 45% da venda do
  produto e o branco (`TAP-BRAN-4060-05`) perto de 8%. Mix de gôndola.
- `JDCP-BRAN-CASAL-01`: em ruptura e sem pedido em trânsito. A Katrina Têxtil é o
  fornecedor mais barato dele.
- `TBC-BEGE-70140-02`: em ruptura e num pedido `enviado` da Katrina Têxtil com a data
  prevista de entrega vencida há 10 dias.
- `PM-AMAR-3040-01`: vendia uns 4 por dia, não vendeu nos dois últimos dias abertos e
  está sem estoque. Queda de venda sem estoque.

`--skus N` acrescenta N SKUs sintéticos (`SINT0001-...`), para medir escala.
"""
from __future__ import annotations

import argparse
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.db.engine import get_engine
from src.inventory.schemas import STATUS_EM_TRANSITO

SEED = 42
PRECO_SOBE_POR_MES = 0.01
HISTORY_MONTHS = 24
DIAS_COM_VENDA_DIARIA = 90
MESES_COM_VENDA_MENSAL = HISTORY_MONTHS - DIAS_COM_VENDA_DIARIA // 30
DIAS_ABERTOS_POR_MES = 26
DOMINGO = 6
LOTE_DE_INSERCAO = 5000

TAPETE_MARROM = "TAP-MARR-4060-01"
TAPETE_BRANCO = "TAP-BRAN-4060-05"
RUPTURA_SEM_PEDIDO = "JDCP-BRAN-CASAL-01"
RUPTURA_COM_PEDIDO_ATRASADO = "TBC-BEGE-70140-02"
QUEDA_SEM_ESTOQUE = "PM-AMAR-3040-01"
DIAS_DE_ATRASO = 10
KATRINA = "Katrina Têxtil"


@dataclass(frozen=True)
class ProdutoSpec:
    nome: str
    categoria: str
    cores: tuple[str, ...]
    tamanhos: tuple[str, ...]
    gramaturas: tuple[int | None, ...]
    material: str
    sigla: str | None = None


@dataclass(frozen=True)
class Cenario:
    """`venda_diaria` fixa a venda média por dia aberto, sem sazonalidade. `cobertura_dias`
    fixa o disponível final em dias da giro dos últimos 6 meses fechados. `ultimas_vendas`
    são as vendas dos últimos dias abertos, do mais antigo até ontem."""

    venda_diaria: float | None = None
    cobertura_dias: float | None = None
    ultimas_vendas: tuple[int, ...] = ()
    fornecedor_mais_barato: str | None = None


CENARIOS: dict[str, Cenario] = {
    TAPETE_MARROM: Cenario(venda_diaria=10, cobertura_dias=45, ultimas_vendas=(5, 0)),
    "TAP-CINZ-4060-02": Cenario(venda_diaria=5, cobertura_dias=50),
    "TAP-AZUL-4060-03": Cenario(venda_diaria=3.4, cobertura_dias=55),
    "TAP-BEGE-4060-04": Cenario(venda_diaria=2.2, cobertura_dias=60),
    TAPETE_BRANCO: Cenario(venda_diaria=1.8, cobertura_dias=70),
    RUPTURA_SEM_PEDIDO: Cenario(cobertura_dias=8, fornecedor_mais_barato=KATRINA),
    RUPTURA_COM_PEDIDO_ATRASADO: Cenario(cobertura_dias=4, fornecedor_mais_barato=KATRINA),
    QUEDA_SEM_ESTOQUE: Cenario(venda_diaria=4, cobertura_dias=0, ultimas_vendas=(0, 0)),
}


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
    ProdutoSpec(
        "Tapete Banheiro", "banho",
        ("marrom", "cinza", "azul", "bege", "branco"),
        ("40x60",),
        (None,), "algodão com base antiderrapante", sigla="TAP",
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
    FornecedorSpec(KATRINA, "12.345.678/0001-90", "30/60/90", 12_000, 35),
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
    "banho": (0, 3, 4),
}

PRECO_BASE: dict[str, int] = {
    "felpudo": 1800,
    "jogo_cama": 8500,
    "mesa": 2400,
    "cozinha": 600,
    "banho": 1500,
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

_CATEGORIAS_SINTETICAS = ("felpudo", "jogo_cama", "mesa", "cozinha")
_CORES_SINTETICAS = ("branco", "bege", "cinza", "azul", "verde")

_UUID_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000000")


def _uuid(namespace: str, key: str) -> uuid.UUID:
    return uuid.uuid5(_UUID_NAMESPACE, f"{namespace}:{key}")


def _rng(*partes: str) -> random.Random:
    return random.Random(":".join((str(SEED), *partes)))


def _sku_code(spec: ProdutoSpec, cor: str, tamanho: str, idx: int) -> str:
    parts = spec.sigla or "".join(w[0] for w in spec.nome.split() if w).upper()[:4]
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


def _inicio_do_mes(dia: date, meses_atras: int = 0) -> datetime:
    mes = dia.year * 12 + dia.month - 1 - meses_atras
    return datetime(mes // 12, mes % 12 + 1, 1, tzinfo=UTC)


def _venda_do_dia(rng: random.Random, media: float) -> int:
    # Pouca variação em volta da média, para nenhum SKU fora dos cenários parecer ter
    # parado de vender.
    return int(media * rng.uniform(0.8, 1.2) + rng.random())


def _produtos_sinteticos(n_skus: int) -> tuple[ProdutoSpec, ...]:
    produtos = []
    for p in range(0, n_skus, len(_CORES_SINTETICAS)):
        numero = p // len(_CORES_SINTETICAS) + 1
        produtos.append(
            ProdutoSpec(
                f"Produto Sintético {numero:04d}",
                _CATEGORIAS_SINTETICAS[numero % len(_CATEGORIAS_SINTETICAS)],
                _CORES_SINTETICAS[: min(len(_CORES_SINTETICAS), n_skus - p)],
                ("único",),
                (None,),
                "sintético",
                sigla=f"SINT{numero:04d}",
            )
        )
    return tuple(produtos)


class _Insercoes:
    """Insere em lotes, para o modo de escala não guardar milhões de linhas na memória."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn
        self._linhas: dict[str, list[dict]] = {}

    def add(self, sql: str, linha: dict) -> None:
        linhas = self._linhas.setdefault(sql, [])
        linhas.append(linha)
        if len(linhas) >= LOTE_DE_INSERCAO:
            self._gravar(sql)

    def _gravar(self, sql: str) -> None:
        linhas = self._linhas.pop(sql, [])
        if linhas:
            self._conn.execute(text(sql), linhas)

    def terminar(self) -> None:
        for sql in list(self._linhas):
            self._gravar(sql)


_INSERT_VENDA = """
    INSERT INTO erp.vendas
      (id, sku_id, quantidade, valor_unitario_reais, data, cliente_ref)
    VALUES
      (:id, :sku_id, :quantidade, :valor_unitario_reais, :data, :cliente_ref)
"""
_INSERT_MOVIMENTACAO = """
    INSERT INTO erp.movimentacoes_estoque
      (id, sku_id, tipo, quantidade, data, referencia_tipo, referencia_id, observacao)
    VALUES
      (:id, :sku_id, :tipo, :quantidade, :data, :referencia_tipo, :referencia_id, :observacao)
"""
_INSERT_SNAPSHOT = """
    INSERT INTO erp.estoque_snapshot
      (sku_id, quantidade_disponivel, quantidade_reservada, atualizado_em)
    VALUES
      (:sku_id, :quantidade_disponivel, :quantidade_reservada, :atualizado_em)
"""


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


def _seed_produtos_e_skus(
    conn: Connection, produtos: tuple[ProdutoSpec, ...], inicio: datetime
) -> list[dict]:
    produtos_rows = []
    skus_rows = []
    skus_por_id: list[dict] = []

    for spec in produtos:
        produto_id = _uuid("produto", spec.nome)
        produtos_rows.append(
            {
                "id": produto_id,
                "nome": spec.nome,
                "categoria": spec.categoria,
                "descricao": f"{spec.nome} - {spec.material}",
                "ativo": True,
                "criado_em": inicio,
            }
        )
        idx = 0
        for cor in spec.cores:
            for tamanho in spec.tamanhos:
                for gramatura in spec.gramaturas:
                    idx += 1
                    sku_id = _uuid("sku", f"{spec.nome}|{cor}|{tamanho}|{gramatura}")
                    code = _sku_code(spec, cor, tamanho, idx)
                    sku_row = {
                        "id": sku_id,
                        "produto_id": produto_id,
                        "sku_code": code,
                        "cor": cor,
                        "tamanho": tamanho,
                        "gramatura": gramatura,
                        "material": spec.material,
                        "ativo": True,
                        "criado_em": inicio,
                    }
                    skus_rows.append(sku_row)
                    skus_por_id.append(
                        {
                            **sku_row,
                            "categoria": spec.categoria,
                            "produto_nome": spec.nome,
                        }
                    )

    insercoes = _Insercoes(conn)
    for row in produtos_rows:
        insercoes.add(
            """
            INSERT INTO erp.produtos (id, nome, categoria, descricao, ativo, criado_em)
            VALUES (:id, :nome, :categoria, :descricao, :ativo, :criado_em)
            """,
            row,
        )
    insercoes.terminar()
    for row in skus_rows:
        insercoes.add(
            """
            INSERT INTO erp.skus (id, produto_id, sku_code, cor, tamanho, gramatura, material, ativo, criado_em)
            VALUES (:id, :produto_id, :sku_code, :cor, :tamanho, :gramatura, :material, :ativo, :criado_em)
            """,
            row,
        )
    insercoes.terminar()
    return skus_por_id


def _seed_fornecedores(conn: Connection, inicio: datetime) -> list[dict]:
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
                "criado_em": inicio,
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


def _relacao(rng: random.Random, fornecedor: dict, sku: dict, agora: datetime) -> dict:
    return {
        "fornecedor_id": fornecedor["id"],
        "sku_id": sku["id"],
        "preco_unitario_atual": int(PRECO_BASE[sku["categoria"]] * rng.uniform(0.85, 1.25)),
        "moq_unidades": rng.choice((24, 36, 48, 60, 120)),
        "lead_time_dias_observado": max(
            1,
            fornecedor["lead_time_dias_contratado"] + rng.randint(-5, 12),
        ),
        "ativo": True,
        "atualizado_em": agora,
    }


def _seed_fornecedor_skus(
    conn: Connection,
    fornecedores: list[dict],
    skus: list[dict],
    agora: datetime,
) -> list[dict]:
    relacoes = []
    for sku in skus:
        rng = _rng("fornecedores", sku["sku_code"])
        candidatos_idx = CATEGORIA_FORNECEDORES[sku["categoria"]]
        n = rng.randint(2, min(3, len(candidatos_idx)))
        do_sku = [_relacao(rng, fornecedores[i], sku, agora) for i in rng.sample(candidatos_idx, k=n)]

        cenario = CENARIOS.get(sku["sku_code"])
        if cenario is not None and cenario.fornecedor_mais_barato is not None:
            preferido = next(f for f in fornecedores if f["nome"] == cenario.fornecedor_mais_barato)
            outros = [r for r in do_sku if r["fornecedor_id"] != preferido["id"]]
            relacao = _relacao(rng, preferido, sku, agora)
            relacao["preco_unitario_atual"] = int(min(r["preco_unitario_atual"] for r in outros) * 0.9)
            relacao["moq_unidades"] = 24
            do_sku = [*outros, relacao]
        relacoes.extend(do_sku)

    insercoes = _Insercoes(conn)
    for relacao in relacoes:
        insercoes.add(
            """
            INSERT INTO erp.fornecedores_skus
              (fornecedor_id, sku_id, preco_unitario_atual, moq_unidades,
               lead_time_dias_observado, ativo, atualizado_em)
            VALUES
              (:fornecedor_id, :sku_id, :preco_unitario_atual, :moq_unidades,
               :lead_time_dias_observado, :ativo, :atualizado_em)
            """,
            relacao,
        )
    insercoes.terminar()
    return relacoes


def _dias_abertos(agora: datetime) -> list[datetime]:
    dias = (agora - timedelta(days=DIAS_COM_VENDA_DIARIA - d) for d in range(DIAS_COM_VENDA_DIARIA))
    return [dia for dia in dias if dia.weekday() != DOMINGO]


def _seed_historico(
    conn: Connection,
    skus: list[dict],
    relacoes: list[dict],
    agora: datetime,
) -> None:
    insercoes = _Insercoes(conn)
    dias_abertos = _dias_abertos(agora)
    preco_de_compra: dict[uuid.UUID, int] = {}
    for rel in relacoes:
        preco_de_compra.setdefault(rel["sku_id"], rel["preco_unitario_atual"])
    for sku in skus:
        _seed_historico_do_sku(insercoes, sku, preco_de_compra[sku["id"]], dias_abertos, agora)
    insercoes.terminar()


def _seed_historico_do_sku(
    insercoes: _Insercoes,
    sku: dict,
    preco_de_compra: int,
    dias_abertos: list[datetime],
    agora: datetime,
) -> None:
    inicio = agora - timedelta(days=HISTORY_MONTHS * 30)
    inicio_da_giro = _inicio_do_mes(agora.date(), 6)
    fim_da_giro = _inicio_do_mes(agora.date())
    rng = _rng("historico", sku["sku_code"])
    cenario = CENARIOS.get(sku["sku_code"], Cenario())
    if cenario.venda_diaria is not None:
        giro_mensal = cenario.venda_diaria * DIAS_ABERTOS_POR_MES
    else:
        giro_mensal = _giro_alvo(rng, sku["categoria"])

    def sazonalidade(mes: int) -> float:
        return 1.0 if cenario.venda_diaria is not None else MESES_SAZONALIDADE[mes]

    preco_venda_unit = int(preco_de_compra * rng.uniform(1.35, 1.75))
    vendido_na_giro = 0

    def movimentacao(chave: str, tipo: str, quantidade: int, data: datetime, **resto: object) -> None:
        insercoes.add(
            _INSERT_MOVIMENTACAO,
            {
                "id": _uuid(chave, f"{sku['id']}|{data.isoformat()}"),
                "sku_id": sku["id"],
                "tipo": tipo,
                "quantidade": quantidade,
                "data": data,
                "referencia_tipo": resto.get("referencia_tipo", "ajuste_manual"),
                "referencia_id": resto.get("referencia_id"),
                "observacao": resto.get("observacao"),
            },
        )

    estoque = int(giro_mensal * rng.uniform(1.5, 3.0))
    movimentacao("mov_init", "entrada_compra", estoque, inicio, observacao="Saldo inicial de seed")

    def vender(qtd: int, data_venda: datetime) -> None:
        nonlocal estoque, vendido_na_giro
        if qtd > estoque:
            reposicao = int(giro_mensal * rng.uniform(1.0, 2.0)) + qtd
            movimentacao(
                "mov_repo",
                "entrada_compra",
                reposicao,
                data_venda - timedelta(hours=1),
                referencia_tipo="pedido_compra",
                observacao="Reposição sazonal",
            )
            estoque += reposicao
        venda_id = _uuid("venda", f"{sku['id']}|{data_venda.isoformat()}")
        insercoes.add(
            _INSERT_VENDA,
            {
                "id": venda_id,
                "sku_id": sku["id"],
                "quantidade": qtd,
                "valor_unitario_reais": preco_venda_unit,
                "data": data_venda,
                "cliente_ref": f"varejista-{rng.randint(1, 40):03d}",
            },
        )
        movimentacao(
            "mov_venda",
            "saida_venda",
            qtd,
            data_venda,
            referencia_tipo="venda",
            referencia_id=venda_id,
        )
        estoque -= qtd
        if inicio_da_giro <= data_venda < fim_da_giro:
            vendido_na_giro += qtd

    for mes_offset in range(MESES_COM_VENDA_MENSAL):
        data_mes = inicio + timedelta(days=mes_offset * 30)
        demanda_mes = max(1, int(giro_mensal * sazonalidade(data_mes.month) * rng.uniform(0.85, 1.15)))

        vendas_do_mes = rng.randint(4, 12)
        pesos = [rng.uniform(0.6, 1.4) for _ in range(vendas_do_mes)]
        total_peso = sum(pesos)
        dias_do_mes = sorted(rng.sample(range(28), k=vendas_do_mes))
        for peso, dia in zip(pesos, dias_do_mes):
            qtd = max(1, int(demanda_mes * peso / total_peso))
            vender(qtd, data_mes + timedelta(days=dia, hours=rng.randint(11, 20)))

        if mes_offset in (5, 11, 17) and rng.random() < 0.4:
            ajuste = min(estoque, rng.randint(1, 3))
            if ajuste > 0:
                movimentacao(
                    "mov_aj",
                    "ajuste_negativo",
                    ajuste,
                    data_mes + timedelta(days=28),
                    observacao="Perda de inventário",
                )
                estoque -= ajuste

    forcados = dict(zip(dias_abertos[len(dias_abertos) - len(cenario.ultimas_vendas):], cenario.ultimas_vendas))
    for dia in dias_abertos:
        media = giro_mensal * sazonalidade(dia.month) / DIAS_ABERTOS_POR_MES
        qtd = forcados.get(dia, _venda_do_dia(rng, media))
        hora = rng.randint(11, 20)
        if qtd > 0:
            vender(qtd, dia + timedelta(hours=hora))

    if cenario.cobertura_dias is not None:
        alvo = round(vendido_na_giro / 6 / 30 * cenario.cobertura_dias)
        reservada = 0
    else:
        alvo = max(1, int(giro_mensal * rng.uniform(0.5, 4.0)))
        reservada = max(0, int(alvo * rng.uniform(0.0, 0.15)))
    delta = alvo - estoque
    if delta > 0:
        movimentacao(
            "mov_final_pos",
            "entrada_compra",
            delta,
            agora - timedelta(days=7),
            referencia_tipo="pedido_compra",
            observacao="Recebimento recente",
        )
    elif delta < 0:
        movimentacao(
            "mov_final_neg",
            "ajuste_negativo",
            -delta,
            agora - timedelta(days=3),
            observacao="Ajuste de cobertura",
        )
    estoque = alvo

    insercoes.add(
        _INSERT_SNAPSHOT,
        {
            "sku_id": sku["id"],
            "quantidade_disponivel": estoque - reservada,
            "quantidade_reservada": reservada,
            "atualizado_em": agora,
        },
    )


def _seed_pedidos_compra(
    conn: Connection,
    fornecedores: list[dict],
    relacoes: list[dict],
    skus: list[dict],
    agora: datetime,
) -> None:
    rng = _rng("pedidos")
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

    code_por_sku = {sku["id"]: sku["sku_code"] for sku in skus}
    rel_por_fornecedor: dict[uuid.UUID, list[dict]] = {}
    for rel in relacoes:
        rel_por_fornecedor.setdefault(rel["fornecedor_id"], []).append(rel)

    pedidos_rows: list[dict] = []
    itens_rows: list[dict] = []

    def pedido(
        pedido_id: uuid.UUID,
        fornecedor: dict,
        status: str,
        item_rels: list[dict],
        criado_em: datetime,
        enviado_em: datetime | None,
        recebido_em: datetime | None,
        data_prevista: date | None,
    ) -> None:
        valor_total = 0
        for item_idx, rel in enumerate(item_rels):
            qtd = rel["moq_unidades"] * rng.randint(1, 3)
            # Pedido mais antigo saiu mais barato (1% por mês até hoje), para o histórico
            # de preço ter o que mostrar na negociação com o representante.
            meses_atras = (agora - criado_em).days / 30
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
                "aprovado_em": criado_em + timedelta(days=2) if status != "rascunho" else None,
                "enviado_em": enviado_em,
                "recebido_em": recebido_em,
                "data_prevista_entrega": data_prevista,
                "valor_total_reais": valor_total,
                "observacao": None,
            }
        )

    for idx, status in enumerate(ordered_status):
        fornecedor = fornecedores[idx % len(fornecedores)]
        lead_time = timedelta(days=fornecedor["lead_time_dias_contratado"])
        rels = rel_por_fornecedor[fornecedor["id"]]
        if status in STATUS_EM_TRANSITO:
            # Os pedidos em trânsito são recentes e estão no prazo: o único atrasado é o do cenário.
            rels = [r for r in rels if code_por_sku[r["sku_id"]] not in CENARIOS]
            criado_em = agora - timedelta(days=5 + 2 * (len(ordered_status) - idx))
        else:
            criado_em = agora - timedelta(days=180 - idx * 10)
        enviado_em = (
            criado_em + timedelta(days=3)
            if status in ("enviado", "recebido_parcial", "recebido_total")
            else None
        )
        recebido_em = None
        if enviado_em is not None and status == "recebido_total":
            recebido_em = enviado_em + lead_time
        elif enviado_em is not None and status == "recebido_parcial":
            recebido_em = agora - timedelta(days=2)
        n_itens = rng.randint(3, 6)
        pedido(
            _uuid("pedido", f"{idx}|{status}"),
            fornecedor,
            status,
            rng.sample(rels, k=min(n_itens, len(rels))),
            criado_em,
            enviado_em,
            recebido_em,
            (enviado_em + lead_time).date() if enviado_em is not None else None,
        )

    katrina = next(f for f in fornecedores if f["nome"] == KATRINA)
    rels_katrina = sorted(
        (r for r in rel_por_fornecedor[katrina["id"]] if code_por_sku[r["sku_id"]] not in CENARIOS),
        key=lambda r: code_por_sku[r["sku_id"]],
    )
    rel_do_cenario = next(
        r for r in rel_por_fornecedor[katrina["id"]] if code_por_sku[r["sku_id"]] == RUPTURA_COM_PEDIDO_ATRASADO
    )
    data_prevista = (agora - timedelta(days=DIAS_DE_ATRASO)).date()
    enviado_em = datetime.combine(data_prevista, datetime.min.time(), UTC) - timedelta(
        days=katrina["lead_time_dias_contratado"]
    )
    pedido(
        _uuid("pedido", "atrasado"),
        katrina,
        "enviado",
        [rel_do_cenario, *rels_katrina[:2]],
        enviado_em - timedelta(days=3),
        enviado_em,
        None,
        data_prevista,
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


def run(skus_extras: int = 0) -> None:
    agora = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    inicio = agora - timedelta(days=HISTORY_MONTHS * 30)
    produtos = PRODUTOS + _produtos_sinteticos(skus_extras)
    engine = get_engine()
    with engine.begin() as conn:
        _wipe(conn)
        skus = _seed_produtos_e_skus(conn, produtos, inicio)
        fornecedores = _seed_fornecedores(conn, inicio)
        relacoes = _seed_fornecedor_skus(conn, fornecedores, skus, agora)
        _seed_historico(conn, skus, relacoes, agora)
        _seed_pedidos_compra(conn, fornecedores, relacoes, skus, agora)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Popula o ERP fake.")
    parser.add_argument("--skus", type=int, default=0, help="SKUs sintéticos a mais, para medir escala")
    run(parser.parse_args().skus)
