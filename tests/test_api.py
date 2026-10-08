import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import main  # noqa: E402


@pytest.fixture
def client():
    main.gerenciador.historico.clear()
    return TestClient(main.app)


def test_painel_carrega(client):
    assert client.get("/").status_code == 200


def test_criar_e_listar(client):
    r = client.post("/api/notificacoes", json={"titulo": "Oi", "nivel": "info"})
    assert r.status_code == 201
    assert client.get("/api/notificacoes").json()[0]["titulo"] == "Oi"


def test_validacao(client):
    r = client.post("/api/notificacoes", json={"titulo": "", "nivel": "inexistente"})
    assert r.status_code == 422


def test_websocket_recebe_em_tempo_real(client):
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["tipo"] == "historico"
        client.post("/api/notificacoes", json={"titulo": "Ao vivo", "nivel": "alerta"})
        msg = ws.receive_json()
        assert msg["tipo"] == "notificacao"
        assert msg["item"]["titulo"] == "Ao vivo"


def test_historico_para_quem_entra_depois(client):
    client.post("/api/notificacoes", json={"titulo": "Antiga", "nivel": "info"})
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["itens"][0]["titulo"] == "Antiga"


def test_chave_de_api(client, monkeypatch):
    monkeypatch.setattr(main, "API_KEY", "segredo")
    corpo = {"titulo": "X", "nivel": "info"}
    assert client.post("/api/notificacoes", json=corpo).status_code == 401
    ok = client.post("/api/notificacoes", json=corpo, headers={"X-API-Key": "segredo"})
    assert ok.status_code == 201
