"""Exemplo de como outro script/serviço dispara uma notificação (só biblioteca padrão)."""
import json
import os
import urllib.request

URL = os.getenv("NOTIF_URL", "http://localhost:8000/api/notificacoes")
CHAVE = os.getenv("NOTIF_API_KEY", "")


def notificar(titulo: str, mensagem: str = "", nivel: str = "info") -> dict:
    corpo = json.dumps({"titulo": titulo, "mensagem": mensagem, "nivel": nivel}).encode()
    cabecalhos = {"Content-Type": "application/json"}
    if CHAVE:
        cabecalhos["X-API-Key"] = CHAVE
    req = urllib.request.Request(URL, data=corpo, headers=cabecalhos, method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.load(resp)


if __name__ == "__main__":
    print(notificar("Backup concluído", "Servidor FS01", "sucesso"))
    print(notificar("Muitas tentativas de login", "5 falhas em 1 minuto", "critico"))
