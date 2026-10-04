"""Testes HTTP das notificações (`/notificacoes` e `/notificacoes/vistas`): a varredura
abre e fecha os episódios de ruptura e de entrega atrasada, o aviso notifica na hora e o
cursor do usuário separa lidas de não lidas. Cenário em `cenario_painel.py`: hoje é
01/10/2026 e `ZERADO`, `SEM_FORNECEDOR`, `MAIS_URGENTE`, `URGENTE` e `PISO` já estão em
ruptura. O usuário logado é lido do repositório em memória a cada requisição, como a
sessão faz de verdade, para o cursor gravado valer na próxima chamada."""
from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from src.api.tests.cenario_painel import (
    BOA_VISTA,
    MAIS_URGENTE,
    PISO,
    REGULAR,
    SEM_FORNECEDOR,
    URGENTE,
    ZERADO,
    Cenario,
    atrasar,
    avisar,
    client,  # noqa: F401 (fixture)
    decidir,
    preparar,
)
from src.catalog.schemas import SKU
from src.main import app
from src.politica_compra.schemas import MotivoAlerta
from src.usuarios.dependencies import usuario_atual
from src.usuarios.schemas import Papel
from tests.fakes import make_estoque, make_usuario

EM_RUPTURA = sorted(s.sku_code for s in (ZERADO, SEM_FORNECEDOR, MAIS_URGENTE, URGENTE, PISO))


def entrar(cenario: Cenario, *papeis: Papel, nome: str = "Carla") -> None:
    usuario = make_usuario(nome, papeis=list(papeis))
    cenario.usuarios.gravar(usuario)
    app.dependency_overrides[usuario_atual] = lambda: cenario.usuarios.por_id(usuario.id)


def caixa(client: TestClient) -> dict:
    response = client.get("/notificacoes")
    assert response.status_code == 200, response.text
    return response.json()


def do_tipo(resposta: dict, tipo: str) -> list[dict]:
    return [n for n in resposta["notificacoes"] if n["tipo"] == tipo]


def rupturas(resposta: dict) -> list[str]:
    return sorted(n["sku_code"] for n in do_tipo(resposta, "ruptura"))


def disponivel(cenario: Cenario, sku: SKU, quantidade: int) -> None:
    cenario.erp.estoques_por_sku[sku.sku_code] = make_estoque(disponivel=quantidade)


def passar(cenario: Cenario, minutos: int = 10) -> None:
    cenario.relogio.agora += timedelta(minutes=minutos)


def test_cada_sku_em_ruptura_notifica_o_comprador_com_os_numeros_do_momento(client: TestClient) -> None:
    cenario = preparar()
    entrar(cenario, "comprador")

    resposta = caixa(client)

    assert rupturas(resposta) == EM_RUPTURA
    assert resposta["nao_lidas"] == 5
    zerado = next(n for n in do_tipo(resposta, "ruptura") if n["sku_code"] == ZERADO.sku_code)
    assert zerado["detalhe"] == {
        "produto_nome": "Toalha Banho Conforto",
        "cor": "lilás",
        "tamanho": "70x140",
        "disponivel": 0,
        "cobertura_dias": 0.0,
    }
    assert zerado["aberto_em"] == "2026-10-01T09:00:00Z"
    assert zerado["fechado_em"] is None
    assert zerado["lida"] is False


def test_varrer_de_novo_nao_notifica_de_novo(client: TestClient) -> None:
    cenario = preparar()
    entrar(cenario, "comprador")
    caixa(client)
    passar(cenario)

    resposta = caixa(client)

    assert rupturas(resposta) == EM_RUPTURA
    assert resposta["nao_lidas"] == 5


def test_sku_que_entra_em_ruptura_abre_uma_notificacao_nova(client: TestClient) -> None:
    cenario = preparar()
    entrar(cenario, "comprador")
    caixa(client)
    passar(cenario)

    disponivel(cenario, REGULAR, 30)
    resposta = caixa(client)

    assert resposta["notificacoes"][0]["sku_code"] == REGULAR.sku_code
    assert resposta["notificacoes"][0]["aberto_em"] == "2026-10-01T09:10:00Z"
    assert resposta["nao_lidas"] == 6


def test_sair_da_ruptura_fecha_e_voltar_abre_outro_episodio(client: TestClient) -> None:
    cenario = preparar()
    entrar(cenario, "comprador")
    disponivel(cenario, REGULAR, 30)
    caixa(client)

    passar(cenario)
    disponivel(cenario, REGULAR, 150)
    caixa(client)
    passar(cenario)
    disponivel(cenario, REGULAR, 30)
    resposta = caixa(client)

    do_regular = [n for n in do_tipo(resposta, "ruptura") if n["sku_code"] == REGULAR.sku_code]
    assert [(n["aberto_em"], n["fechado_em"]) for n in do_regular] == [
        ("2026-10-01T09:20:00Z", None),
        ("2026-10-01T09:00:00Z", "2026-10-01T09:10:00Z"),
    ]


def test_sku_com_decisao_vigente_nao_notifica_ruptura(client: TestClient) -> None:
    cenario = preparar()
    entrar(cenario, "comprador")
    decidir(client, ZERADO)

    resposta = caixa(client)

    assert ZERADO.sku_code not in rupturas(resposta)
    assert len(rupturas(resposta)) == 4


def test_decisao_fecha_a_ruptura_e_ela_volta_quando_a_decisao_vence(client: TestClient) -> None:
    cenario = preparar()
    entrar(cenario, "comprador")
    caixa(client)

    decidir(client, ZERADO)
    passar(cenario)
    fechada = next(n for n in do_tipo(caixa(client), "ruptura") if n["sku_code"] == ZERADO.sku_code)
    cenario.relogio.agora += timedelta(days=7)
    resposta = caixa(client)

    assert fechada["fechado_em"] == "2026-10-01T09:10:00Z"
    do_zerado = [n for n in do_tipo(resposta, "ruptura") if n["sku_code"] == ZERADO.sku_code]
    assert [n["fechado_em"] for n in do_zerado] == [None, "2026-10-01T09:10:00Z"]


def test_ruptura_fora_dos_motivos_da_politica_nao_notifica(client: TestClient) -> None:
    cenario = preparar(motivos_de_alerta=(MotivoAlerta.ENTREGA_ATRASADA,))
    entrar(cenario, "comprador")

    assert caixa(client) == {"notificacoes": [], "nao_lidas": 0}


def test_pedido_com_entrega_atrasada_notifica_uma_vez_e_a_cobranca_fecha(client: TestClient) -> None:
    cenario = preparar()
    entrar(cenario, "comprador")
    pedido = atrasar(cenario, BOA_VISTA, (REGULAR, 120), (URGENTE, 60))

    antes = do_tipo(caixa(client), "entrega_atrasada")
    passar(cenario)
    resposta = client.post(f"/pedidos/{pedido.id}/cobrancas", json={})
    assert resposta.status_code == 201, resposta.text
    depois = do_tipo(caixa(client), "entrega_atrasada")

    assert [(n["pedido_id"], n["sku_code"], n["fechado_em"]) for n in antes] == [(str(pedido.id), None, None)]
    assert antes[0]["detalhe"] == {
        "fornecedor_nome": "Boa Vista Têxtil",
        "data_prevista_entrega": "2026-09-30",
        "dias_de_atraso": 1,
        "skus": sorted([REGULAR.sku_code, URGENTE.sku_code]),
    }
    assert [n["fechado_em"] for n in depois] == ["2026-10-01T09:10:00Z"]


def test_cobranca_vencida_notifica_a_entrega_de_novo(client: TestClient) -> None:
    cenario = preparar()
    entrar(cenario, "comprador")
    pedido = atrasar(cenario, BOA_VISTA, (REGULAR, 120))
    client.post(f"/pedidos/{pedido.id}/cobrancas", json={"nova_previsao": "2026-10-02"})
    caixa(client)

    cenario.relogio.agora += timedelta(days=2)
    resposta = caixa(client)

    assert [n["fechado_em"] for n in do_tipo(resposta, "entrega_atrasada")] == [None]


def test_aviso_da_equipe_de_vendas_notifica_o_comprador_na_hora_cada_vez(client: TestClient) -> None:
    cenario = preparar()
    avisar(client, REGULAR, "vendendo_muito", comentario="cliente levou 10")
    passar(cenario)
    avisar(client, REGULAR, "acabou")
    entrar(cenario, "comprador")

    avisos = do_tipo(caixa(client), "aviso")

    assert [(n["sku_code"], n["detalhe"]["tipo"], n["aberto_em"]) for n in avisos] == [
        (REGULAR.sku_code, "acabou", "2026-10-01T09:10:00Z"),
        (REGULAR.sku_code, "vendendo_muito", "2026-10-01T09:00:00Z"),
    ]
    assert avisos[1]["detalhe"] == {
        "produto_nome": "Toalha Banho Conforto",
        "cor": "bege",
        "tamanho": "70x140",
        "tipo": "vendendo_muito",
        "avisado_por": "Pessoa Teste",
        "comentario": "cliente levou 10",
    }


def test_o_cursor_separa_lidas_de_nao_lidas(client: TestClient) -> None:
    cenario = preparar()
    entrar(cenario, "comprador")
    caixa(client)
    passar(cenario)

    assert client.post("/notificacoes/vistas").status_code == 204
    lidas = caixa(client)
    passar(cenario)
    disponivel(cenario, REGULAR, 30)
    resposta = caixa(client)

    assert lidas["nao_lidas"] == 0
    assert all(n["lida"] for n in lidas["notificacoes"])
    assert resposta["nao_lidas"] == 1
    assert [(n["sku_code"], n["lida"]) for n in resposta["notificacoes"] if not n["lida"]] == [
        (REGULAR.sku_code, False)
    ]


def test_o_cursor_e_de_cada_usuario(client: TestClient) -> None:
    cenario = preparar()
    entrar(cenario, "comprador", nome="Carla")
    caixa(client)
    client.post("/notificacoes/vistas")

    entrar(cenario, "comprador", nome="Marcos")

    assert caixa(client)["nao_lidas"] == 5


def test_quem_nao_e_do_papel_de_destino_nao_ve(client: TestClient) -> None:
    cenario = preparar()
    entrar(cenario, "comprador", "vendas", nome="Carla")
    caixa(client)
    avisar(client, REGULAR)

    for papel in ("vendas", "reposicao", "admin"):
        entrar(cenario, papel, nome=f"So {papel}")
        assert caixa(client) == {"notificacoes": [], "nao_lidas": 0}
