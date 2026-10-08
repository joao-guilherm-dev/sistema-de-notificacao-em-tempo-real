# Notificações em tempo real

Sistema de notificações ao vivo com **FastAPI + WebSocket**. Qualquer script ou serviço manda uma notificação por HTTP e todo mundo com o painel aberto recebe na hora, sem recarregar a página.

## Funcionalidades

- Entrega instantânea via WebSocket (toast + lista)
- Histórico recente (últimas 100) para quem abre o painel depois
- 4 níveis: info, sucesso, alerta e crítico, com filtro por nível
- Contador de não lidas no título da aba
- Reconexão automática com espera crescente
- Painel sem dependências externas (um arquivo, sem build)
- Painel protegido contra XSS (o texto nunca é interpretado como HTML)
- Chave de API opcional para proteger o envio

## Como rodar

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
uvicorn main:app --reload
```

Abra http://localhost:8000.

## Enviando notificações

```bash
curl -X POST http://localhost:8000/api/notificacoes \
  -H "Content-Type: application/json" \
  -d '{"titulo":"Backup concluído","mensagem":"Servidor FS01","nivel":"sucesso"}'
```

Em Python, veja [`exemplo_envio.py`](exemplo_envio.py) (usa só a biblioteca padrão).

### Proteger o envio com chave

```bash
set NOTIF_API_KEY=minha-chave        # Windows
export NOTIF_API_KEY=minha-chave     # Linux/macOS
```

Com a variável definida, o `POST` exige o header `X-API-Key`.

## API

| Método | Rota                 | Descrição                                   |
|--------|----------------------|---------------------------------------------|
| GET    | `/`                  | Painel web                                  |
| GET    | `/api/notificacoes`  | Histórico (mais recente primeiro)           |
| POST   | `/api/notificacoes`  | Cria e distribui uma notificação            |
| GET    | `/api/config`        | Informa se o envio exige chave              |
| WS     | `/ws`                | Recebe histórico e notificações ao vivo     |

Campos do `POST`: `titulo` (1–80 caracteres), `mensagem` (até 500, opcional) e `nivel` (`info`, `sucesso`, `alerta` ou `critico`).

## Testes

```bash
pip install -r requirements-dev.txt
pytest
```

## Limitações e próximos passos

- O histórico fica em memória e some quando o servidor reinicia (dá para trocar por SQLite).
- Com vários processos/workers, as conexões não são compartilhadas (a solução é um broker como Redis Pub/Sub).
- Ideias: canais por assunto, autenticação por usuário, notificações do navegador (Notification API).

## Licença

MIT
