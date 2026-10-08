"""
Sistema de notificações em tempo real (FastAPI + WebSocket).

Rodar:
    pip install -r requirements.txt
    uvicorn main:app --reload
    -> abra http://localhost:8000

Enviar notificação de qualquer script/serviço:
    curl -X POST http://localhost:8000/api/notificacoes \
         -H "Content-Type: application/json" \
         -d '{"titulo":"Backup concluído","mensagem":"Servidor FS01","nivel":"sucesso"}'

Proteger o envio com chave (opcional):
    set NOTIF_API_KEY=minha-chave          (Windows)
    export NOTIF_API_KEY=minha-chave       (Linux/macOS)
    e mandar o header  X-API-Key: minha-chave
"""
import os
import secrets
from collections import deque
from datetime import datetime, timezone
from itertools import count
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

API_KEY = os.getenv("NOTIF_API_KEY", "")
HISTORICO_MAX = 100

app = FastAPI(title="Notificações em tempo real")


class NotificacaoIn(BaseModel):
    titulo: str = Field(min_length=1, max_length=80)
    mensagem: str = Field(default="", max_length=500)
    nivel: Literal["info", "sucesso", "alerta", "critico"] = "info"


class Gerenciador:
    """Guarda as conexões abertas e o histórico recente (em memória)."""

    def __init__(self) -> None:
        self.conexoes: set[WebSocket] = set()
        self.historico: deque[dict] = deque(maxlen=HISTORICO_MAX)
        self._ids = count(1)

    async def conectar(self, ws: WebSocket) -> None:
        await ws.accept()
        self.conexoes.add(ws)
        # quem acabou de entrar recebe o que já aconteceu (mais recente primeiro)
        await ws.send_json({"tipo": "historico", "itens": list(self.historico)[::-1]})

    def desconectar(self, ws: WebSocket) -> None:
        self.conexoes.discard(ws)

    async def publicar(self, dados: NotificacaoIn) -> dict:
        item = {
            "id": next(self._ids),
            "ts": datetime.now(timezone.utc).isoformat(),
            **dados.model_dump(),
        }
        self.historico.append(item)
        mortas = []
        for ws in list(self.conexoes):
            try:
                await ws.send_json({"tipo": "notificacao", "item": item})
            except Exception:
                mortas.append(ws)
        for ws in mortas:
            self.desconectar(ws)
        return item


gerenciador = Gerenciador()


def checar_chave(x_api_key: str | None) -> None:
    if API_KEY and not secrets.compare_digest(x_api_key or "", API_KEY):
        raise HTTPException(status_code=401, detail="Chave de API inválida ou ausente.")


@app.get("/api/config")
async def config():
    return {"chave_obrigatoria": bool(API_KEY)}


@app.get("/api/notificacoes")
async def listar():
    return list(gerenciador.historico)[::-1]


@app.post("/api/notificacoes", status_code=201)
async def criar(dados: NotificacaoIn, x_api_key: str | None = Header(default=None)):
    checar_chave(x_api_key)
    return await gerenciador.publicar(dados)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await gerenciador.conectar(ws)
    try:
        while True:
            await ws.receive_text()  # o cliente manda "ping" só para manter a conexão viva
    except WebSocketDisconnect:
        pass
    finally:
        gerenciador.desconectar(ws)


@app.get("/", response_class=HTMLResponse)
async def painel():
    return PAINEL_HTML


PAINEL_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Notificações</title>
<style>
  :root {
    --fundo: #0f1722;
    --painel: #172233;
    --borda: #26364d;
    --texto: #e6edf7;
    --suave: #8fa3bf;
    --info: #5aa9ff;
    --sucesso: #4cc38a;
    --alerta: #f2b24c;
    --critico: #ff6b6b;
    --raio: 8px;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--fundo); color: var(--texto);
    font: 15px/1.5 "Segoe UI", system-ui, -apple-system, sans-serif;
  }
  header {
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 16px 24px; border-bottom: 1px solid var(--borda);
  }
  h1 { margin: 0; font-size: 20px; font-weight: 600; }
  .estado { display: flex; align-items: center; gap: 8px; color: var(--suave); font-size: 14px; }
  .ponto { width: 10px; height: 10px; border-radius: 50%; background: var(--critico); }
  .ponto.on { background: var(--sucesso); }
  main {
    display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 24px;
    max-width: 1080px; margin: 0 auto; padding: 24px;
  }
  @media (max-width: 800px) { main { grid-template-columns: 1fr; padding: 16px; } }
  .barra { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 14px; }
  .barra .espaco { flex: 1; }
  button, select, input, textarea {
    font: inherit; color: var(--texto); background: var(--painel);
    border: 1px solid var(--borda); border-radius: var(--raio); padding: 7px 12px;
  }
  button { cursor: pointer; }
  button:hover { border-color: var(--suave); }
  button:focus-visible, select:focus-visible, input:focus-visible, textarea:focus-visible {
    outline: 2px solid var(--info); outline-offset: 2px;
  }
  .filtro[aria-pressed="true"] { background: var(--info); border-color: var(--info); color: #07101c; font-weight: 600; }
  .contador { color: var(--suave); font-size: 14px; }
  ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
  li.item {
    background: var(--painel); border: 1px solid var(--borda); border-left: 4px solid var(--cor);
    border-radius: var(--raio); padding: 10px 14px;
  }
  li.item.nova { background: #1c2b42; }
  li.item .topo { display: flex; justify-content: space-between; gap: 12px; }
  li.item .titulo { font-weight: 600; }
  li.item .hora { color: var(--suave); font-size: 13px; white-space: nowrap; }
  li.item .msg { color: var(--suave); margin-top: 2px; overflow-wrap: anywhere; }
  .vazio { color: var(--suave); padding: 32px 0; text-align: center; }
  .nivel-info { --cor: var(--info); }
  .nivel-sucesso { --cor: var(--sucesso); }
  .nivel-alerta { --cor: var(--alerta); }
  .nivel-critico { --cor: var(--critico); }
  form { display: flex; flex-direction: column; gap: 10px; background: var(--painel);
    border: 1px solid var(--borda); border-radius: var(--raio); padding: 16px; align-self: start; }
  form h2 { margin: 0 0 4px; font-size: 16px; }
  label { display: flex; flex-direction: column; gap: 4px; color: var(--suave); font-size: 14px; }
  textarea { resize: vertical; min-height: 70px; }
  .enviar { background: var(--info); border-color: var(--info); color: #07101c; font-weight: 600; }
  .erro { color: var(--critico); font-size: 14px; min-height: 20px; }
  #toasts { position: fixed; right: 16px; bottom: 16px; display: flex; flex-direction: column;
    gap: 8px; width: min(340px, calc(100vw - 32px)); z-index: 10; }
  .toast {
    background: var(--painel); border: 1px solid var(--borda); border-left: 4px solid var(--cor);
    border-radius: var(--raio); padding: 10px 14px; box-shadow: 0 6px 20px rgba(0, 0, 0, .35);
    animation: entrar .18s ease-out;
  }
  .toast .titulo { font-weight: 600; }
  .toast .msg { color: var(--suave); overflow-wrap: anywhere; }
  @keyframes entrar { from { transform: translateX(16px); opacity: 0; } to { transform: none; opacity: 1; } }
  @media (prefers-reduced-motion: reduce) { .toast { animation: none; } }
</style>
</head>
<body>
<header>
  <h1>Notificações <span class="contador" id="naoLidas"></span></h1>
  <div class="estado" role="status"><span class="ponto" id="ponto"></span><span id="estado">Conectando…</span></div>
</header>

<main>
  <section aria-label="Lista de notificações">
    <div class="barra">
      <button class="filtro" data-nivel="todos" aria-pressed="true">Todas</button>
      <button class="filtro" data-nivel="info" aria-pressed="false">Info</button>
      <button class="filtro" data-nivel="sucesso" aria-pressed="false">Sucesso</button>
      <button class="filtro" data-nivel="alerta" aria-pressed="false">Alerta</button>
      <button class="filtro" data-nivel="critico" aria-pressed="false">Crítico</button>
      <span class="espaco"></span>
      <button id="marcarLidas">Marcar todas como lidas</button>
    </div>
    <ul id="lista"></ul>
  </section>

  <form id="form">
    <h2>Enviar notificação</h2>
    <label>Título
      <input id="titulo" maxlength="80" required placeholder="Ex.: Backup concluído">
    </label>
    <label>Mensagem
      <textarea id="mensagem" maxlength="500" placeholder="Detalhes (opcional)"></textarea>
    </label>
    <label>Nível
      <select id="nivel">
        <option value="info">Info</option>
        <option value="sucesso">Sucesso</option>
        <option value="alerta">Alerta</option>
        <option value="critico">Crítico</option>
      </select>
    </label>
    <label id="campoChave" hidden>Chave de API
      <input id="chave" type="password" autocomplete="off">
    </label>
    <button class="enviar" type="submit">Enviar notificação</button>
    <div class="erro" id="erro" role="alert"></div>
  </form>
</main>

<div id="toasts" aria-live="polite"></div>

<script>
  const $ = (id) => document.getElementById(id);
  let itens = [];
  let filtro = "todos";
  let tentativas = 0;
  const lidas = new Set();

  const NOMES = { info: "Info", sucesso: "Sucesso", alerta: "Alerta", critico: "Crítico" };

  function hora(iso) {
    return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }

  function criarItem(n) {
    const li = document.createElement("li");
    li.className = "item nivel-" + n.nivel + (lidas.has(n.id) ? "" : " nova");

    const topo = document.createElement("div");
    topo.className = "topo";
    const t = document.createElement("span");
    t.className = "titulo";
    t.textContent = n.titulo;          // textContent: nunca interpreta HTML vindo da API
    const h = document.createElement("span");
    h.className = "hora";
    h.textContent = NOMES[n.nivel] + " · " + hora(n.ts);
    topo.append(t, h);
    li.append(topo);

    if (n.mensagem) {
      const m = document.createElement("div");
      m.className = "msg";
      m.textContent = n.mensagem;
      li.append(m);
    }
    return li;
  }

  function desenhar() {
    const visiveis = itens.filter((n) => filtro === "todos" || n.nivel === filtro);
    const lista = $("lista");
    lista.replaceChildren();
    if (!visiveis.length) {
      const v = document.createElement("li");
      v.className = "vazio";
      v.textContent = "Nenhuma notificação por aqui. Envie uma pelo formulário ou pela API.";
      lista.append(v);
    } else {
      visiveis.forEach((n) => lista.append(criarItem(n)));
    }
    const nao = itens.filter((n) => !lidas.has(n.id)).length;
    $("naoLidas").textContent = nao ? "(" + nao + " não lidas)" : "";
    document.title = nao ? "(" + nao + ") Notificações" : "Notificações";
  }

  function toast(n) {
    const el = document.createElement("div");
    el.className = "toast nivel-" + n.nivel;
    const t = document.createElement("div");
    t.className = "titulo";
    t.textContent = n.titulo;
    el.append(t);
    if (n.mensagem) {
      const m = document.createElement("div");
      m.className = "msg";
      m.textContent = n.mensagem;
      el.append(m);
    }
    $("toasts").append(el);
    setTimeout(() => el.remove(), n.nivel === "critico" ? 10000 : 5000);
  }

  function conectar() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(proto + "://" + location.host + "/ws");
    let ping;

    ws.onopen = () => {
      tentativas = 0;
      $("ponto").classList.add("on");
      $("estado").textContent = "Ao vivo";
      ping = setInterval(() => ws.readyState === 1 && ws.send("ping"), 25000);
    };

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.tipo === "historico") {
        itens = msg.itens;
        // o que já estava no servidor quando abri a página não conta como "novo"
        itens.forEach((n) => lidas.add(n.id));
      } else if (msg.tipo === "notificacao") {
        itens.unshift(msg.item);
        toast(msg.item);
      }
      desenhar();
    };

    ws.onclose = () => {
      clearInterval(ping);
      $("ponto").classList.remove("on");
      const espera = Math.min(1000 * 2 ** tentativas++, 15000);
      $("estado").textContent = "Desconectado. Tentando de novo em " + Math.round(espera / 1000) + "s";
      setTimeout(conectar, espera);
    };
  }

  document.querySelectorAll(".filtro").forEach((b) =>
    b.addEventListener("click", () => {
      filtro = b.dataset.nivel;
      document.querySelectorAll(".filtro").forEach((x) => x.setAttribute("aria-pressed", x === b));
      desenhar();
    })
  );

  $("marcarLidas").addEventListener("click", () => {
    itens.forEach((n) => lidas.add(n.id));
    desenhar();
  });

  $("form").addEventListener("submit", async (e) => {
    e.preventDefault();
    $("erro").textContent = "";
    const headers = { "Content-Type": "application/json" };
    if ($("chave").value) headers["X-API-Key"] = $("chave").value;
    const r = await fetch("/api/notificacoes", {
      method: "POST",
      headers,
      body: JSON.stringify({
        titulo: $("titulo").value.trim(),
        mensagem: $("mensagem").value.trim(),
        nivel: $("nivel").value,
      }),
    });
    if (r.ok) {
      $("titulo").value = "";
      $("mensagem").value = "";
    } else if (r.status === 401) {
      $("erro").textContent = "Chave de API inválida. Confira e tente de novo.";
    } else {
      $("erro").textContent = "Não foi possível enviar. Confira os campos.";
    }
  });

  fetch("/api/config").then((r) => r.json()).then((c) => { $("campoChave").hidden = !c.chave_obrigatoria; });

  desenhar();
  conectar();
</script>
</body>
</html>
"""
