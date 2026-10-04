"""Smoke do repositor contra o Postgres real, com o Tapete Banheiro do seed: a vendedora
avisa que a gôndola do tapete marrom está vazia, o repositor verifica e a vendedora vê o
resultado; e o mix de gôndola divide os lugares pela participação nas vendas. No fim, as
fixtures apagam só o que o smoke gravou e devolvem episódios, setores e capacidades."""
from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from scripts.seed import TAPETE_BANHEIRO, TAPETE_BRANCO, TAPETE_MARROM
from src.api.schemas import (
    AvisoGondolaResponse,
    MixDeGondolaResponse,
    PainelDoRepositorResponse,
    ProdutoDaGondolaResponse,
    VerificacaoGondolaResponse,
)
from src.usuarios.schemas import Usuario

pytestmark = pytest.mark.smoke


def _painel_do_repositor(client: TestClient, **filtro: str) -> PainelDoRepositorResponse:
    response = client.get("/reposicao/painel", params=filtro)
    assert response.status_code == 200
    return PainelDoRepositorResponse.model_validate(response.json())


def _notificacoes(client: TestClient, tipo: str) -> list[dict]:
    notificacoes = client.get("/notificacoes").json()["notificacoes"]
    return [n for n in notificacoes if n["tipo"] == tipo and n["sku_code"] == TAPETE_MARROM]


@pytest.mark.usefixtures("episodios_restaurados", "setores_restaurados")
def test_aviso_de_gondola_vazia_do_tapete_e_verificacao(
    client: TestClient, criados: dict[str, list[UUID]], usuario_logado: Usuario
) -> None:
    setores = {s["nome"]: s["id"] for s in client.get("/setores").json()}
    assert client.get(f"/skus/{TAPETE_MARROM}/setor").json()["setor"]["id"] == setores["Tapetes"]

    response = client.post(
        "/avisos-gondola", json={"sku_code": TAPETE_MARROM, "setor_id": setores["Tapetes"], "comentario": "Smoke."}
    )
    assert response.status_code == 201
    aviso = AvisoGondolaResponse.model_validate(response.json())
    criados["avisos_gondola"].append(aviso.id)
    assert aviso.avisado_por == usuario_logado.nome and aviso.disponivel_no_erp > 0

    painel = _painel_do_repositor(client)
    [item] = painel.avisos_de_gondola
    assert item.sku_code == TAPETE_MARROM and item.setor is not None and item.setor.nome == "Tapetes"
    assert [a.id for a in item.avisos] == [aviso.id]
    assert item.queda is not None, "o tapete também parou de vender"
    assert painel.quedas_de_venda == []
    assert _painel_do_repositor(client, setor=setores["Cama"]).avisos_de_gondola == []
    assert _notificacoes(client, "gondola_vazia")[0]["detalhe"]["setor"] == "Tapetes"

    response = client.post(f"/skus/{TAPETE_MARROM}/verificacoes", json={"resultado": "repus"})
    assert response.status_code == 201
    verificacao = VerificacaoGondolaResponse.model_validate(response.json())
    criados["verificacoes_gondola"].append(verificacao.id)

    depois = _painel_do_repositor(client)
    assert depois.avisos_de_gondola == [] and depois.quedas_de_venda == []
    meu = next(a for a in client.get("/avisos/meus").json() if a["id"] == str(aviso.id))
    assert meu["para"] == "repositor" and meu["setor"] == "Tapetes"
    assert meu["verificacao"]["resultado"] == "repus"
    [resposta] = _notificacoes(client, "verificacao_sobre_aviso")
    assert resposta["detalhe"]["resultado"] == "repus"
    alertas = {i["sku_code"]: i for i in client.get("/painel").json()["alertas"]}
    assert TAPETE_MARROM not in alertas, "repus não é estoque divergente"


@pytest.mark.usefixtures("capacidades_restauradas")
def test_mix_de_gondola_do_tapete_do_seed(client: TestClient) -> None:
    [produto] = [
        ProdutoDaGondolaResponse.model_validate(p)
        for p in client.get("/reposicao/produtos", params={"busca": "tapete banheiro"}).json()
    ]
    assert produto.produto_nome == TAPETE_BANHEIRO and produto.skus == 5

    def mix(**params: int) -> MixDeGondolaResponse:
        response = client.get(f"/reposicao/produtos/{produto.produto_id}/mix", params=params)
        assert response.status_code == 200
        return MixDeGondolaResponse.model_validate(response.json())

    com_12 = mix(capacidade=12)
    quantidades = {s.sku_code: s.quantidade or 0 for s in com_12.skus}
    assert sum(quantidades.values()) == 12
    assert com_12.skus[0].sku_code == TAPETE_MARROM and com_12.skus[-1].sku_code == TAPETE_BRANCO
    assert quantidades[TAPETE_MARROM] == max(quantidades.values()) and quantidades[TAPETE_BRANCO] >= 1
    assert 0.35 <= com_12.skus[0].participacao <= 0.55 and com_12.skus[-1].participacao <= 0.15

    response = client.put(f"/reposicao/produtos/{produto.produto_id}/capacidade", json={"capacidade": 12})
    assert response.status_code == 200
    gravada = mix()
    assert gravada.capacidade == gravada.capacidade_gravada == 12
    assert gravada.skus == com_12.skus
    assert client.get(f"/skus/{TAPETE_MARROM}/analise").json()["produto_id"] == str(produto.produto_id)
