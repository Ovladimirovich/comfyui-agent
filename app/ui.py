"""M9 — Minimal UI (чат + preview + progress SSE).

Минимальный веб-сервер поверх существующего ConversationAgent/AssetStore. Не вводит
новых зависимостей (stdlib http.server) и НЕ модифицирует execution core.

Источник истины: docs/PROJECT_SPEC.md, docs/17_ROADMAP.md (M9), docs/11_CONVERSATION_MODEL.md.

Поток (media-agnostic, тот же ConversationAgent):
    POST /turn {session_id, request|capability, params?, assets?}
      → ConversationAgent.turn (в фоновом потоке)
      → SSE /events: start → status(RUNNING) → progress(%) → result|error (с preview active_asset)
    GET /asset/<id>  → байты ассета (preview)
    GET /api/session → контекст session (active_asset / assets / active_job)

Гранулярный progress: WS progress events → on_progress callback → Job.progress → SSE.
Backend limitation: ComfyUI DirectML/CPU НЕ шлёт WS execution events — progress bar
показывает честные 0%→hide (state-based fallback), без fake-процентов.
"""
from __future__ import annotations

import html
import json
import mimetypes
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from app.agent import _build_provider
from app.assets import AssetStore
from app.conversation import ConversationAgent, ConversationContext
from app.context.feedback import FeedbackRecord, FeedbackStore
from app.prompt import CompositePromptBuilder, HeuristicPromptBuilder, PromptContext


class SessionStream:
    """Буфер SSE-событий одной session (replay-safe, без дублей).

    События буферизуются в список; SSE-хендлер читает их последовательно по индексу,
    поэтому подписка до/после старта turn не теряет и не дублирует события.
    """

    TERMINAL = ("result", "error")

    def __init__(self) -> None:
        self._events: list[dict] = []
        self._cond = threading.Condition()
        self._done = False

    def push(self, event: dict) -> None:
        with self._cond:
            self._events.append(event)
            if event.get("type") in self.TERMINAL:
                self._done = True
            self._cond.notify_all()

    def wait_next(self, idx: int, timeout: float = 30.0) -> Optional[dict]:
        with self._cond:
            if idx < len(self._events):
                return self._events[idx]
            if self._done:
                return None
            self._cond.wait(timeout)
            if idx < len(self._events):
                return self._events[idx]
            return None


class ComfyUIServer:
    """Минимальный UI-сервер поверх ConversationAgent.

    Инстанцируется с готовым store (и опционально provider для тестов/inject).
    Один ConversationAgent обслуживает много session (изоляция по session_id).
    """

    def __init__(
        self,
        store: AssetStore,
        agent: Optional[ConversationAgent] = None,
        provider=None,
        prompt_builder=None,  # M12: CompositePromptBuilder (default) or custom
    ) -> None:
        self.store = store
        self.agent = agent or ConversationAgent(store)
        self.provider = provider
        # M12: default to CompositePromptBuilder (LLM fallback to heuristic)
        if prompt_builder is None:
            from app.prompt.llm import LLMPromptBuilder
            llm_builder = None
            try:
                llm_builder = LLMPromptBuilder()
            except Exception:
                pass  # LLM не настроен → fallback на heuristic
            prompt_builder = CompositePromptBuilder(llm_builder=llm_builder)
        self.prompt_builder = prompt_builder
        self.streams: dict[str, SessionStream] = {}
        self._lock = threading.Lock()
        # M17: feedback store
        self.feedback_store = FeedbackStore()

    def stream(self, session_id: str) -> SessionStream:
        with self._lock:
            return self.streams.setdefault(session_id, SessionStream())

    def run_turn(
        self,
        session_id: str,
        capability: Optional[str] = None,
        request: Optional[str] = None,
        params: Optional[dict] = None,
        assets: Optional[dict] = None,
        ws_timeout: int = 15,
    ) -> None:
        """Запустить один ход диалога в фоновом потоке и стримить события в SSE.

        ws_timeout: таймаут WS трекинга (сек). При отсутствии WS execution events
        (DirectML/CPU backend) timeout запускает /history fallback. 15s достаточно
        для fast-fallthrough; реальный WS progress (GPU backends) не затронут.
        """
        stream = self.stream(session_id)

        def _run() -> None:
            try:
                stream.push({
                    "type": "start",
                    "session_id": session_id,
                    "capability": capability,
                    "request": request,
                })
                stream.push({"type": "status", "state": "RUNNING"})

                def _on_progress(value: float, max_val: float) -> None:
                    pct = int(value / max_val * 100) if max_val > 0 else 0
                    stream.push({"type": "progress", "value": value, "max": max_val, "pct": pct})

                job = self.agent.turn(
                    session_id,
                    capability=capability,
                    request=request,
                    params=params,
                    assets=assets,
                    provider=self.provider,
                    ws_timeout=ws_timeout,
                    on_progress=_on_progress,
                )
                ctx: ConversationContext = self.agent.session(session_id)
                stream.push({
                    "type": "result",
                    "state": job.state.value if job is not None else None,
                    "active_asset": ctx.active_asset,
                    "active_workflow": ctx.active_workflow,
                    "active_job": ctx.active_job,
                    "assets": sorted(ctx.assets),
                    "preview": f"/asset/{ctx.active_asset}" if ctx.active_asset else None,
                })
            except Exception as exc:  # ошибка не должна обрушивать поток SSE
                stream.push({
                    "type": "error",
                    "error": str(exc),
                    "kind": type(exc).__name__,
                })

        threading.Thread(target=_run, daemon=True).start()

    def session_state(self, session_id: str) -> dict:
        ctx = self.agent.sessions.get(session_id)
        if ctx is None:
            return {"session_id": session_id, "exists": False}
        data = ctx.as_dict()
        data["exists"] = True
        return data

    def serve_asset(self, asset_id: str):
        asset = self.store.get(asset_id)
        if asset is None:
            return None, None
        with open(asset.path, "rb") as fh:
            return fh.read(), (asset.mime or _mime_for(asset.path))

    # M17: feedback methods
    def record_feedback(self, session_id: str, attempt_id: str, rating: int, comment: str = "") -> dict:
        """Записать обратную связь пользователя."""
        feedback = FeedbackRecord(
            attempt_id=attempt_id,
            session_id=session_id,
            rating=rating,
            comment=comment,
        )
        self.feedback_store.record(feedback)
        return {"ok": True, "attempt_id": attempt_id, "rating": rating}

    def get_feedback_history(self, session_id: str) -> list[dict]:
        """Получить историю обратной связи для сессии."""
        records = self.feedback_store.get_for_session(session_id)
        return [r.to_dict() for r in records]


def _mime_for(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


_INDEX_HTML = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ComfyUI Agent — M9 UI</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #0f1115; color: #e6e6e6; }
  header { padding: 12px 16px; background: #161a22; border-bottom: 1px solid #2a2f3a; }
  #app { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 16px; height: calc(100vh - 120px); }
  #chat { display: flex; flex-direction: column; }
  #log { flex: 1; overflow-y: auto; border: 1px solid #2a2f3a; border-radius: 8px; padding: 8px; background: #11151c; }
  .msg { margin: 6px 0; padding: 6px 10px; border-radius: 8px; max-width: 90%; }
  .user { background: #1e3a5f; align-self: flex-end; margin-left: auto; }
  .bot { background: #1d2530; }
  .sys { color: #8aa0b6; font-size: 12px; }
  #controls { display: flex; gap: 8px; margin-top: 8px; }
  #controls input { flex: 1; padding: 8px; border-radius: 8px; border: 1px solid #2a2f3a; background: #0c0f14; color: #e6e6e6; }
  #controls button { padding: 8px 16px; border-radius: 8px; border: none; background: #2f6df0; color: #fff; cursor: pointer; }
  #preview { border: 1px solid #2a2f3a; border-radius: 8px; background: #11151c; display: flex; align-items: center; justify-content: center; overflow: hidden; }
  #preview img, #preview video, #preview audio { max-width: 100%; max-height: 100%; }
  #status { color: #8aa0b6; font-size: 13px; min-height: 18px; }
  #progress-wrap { height: 6px; background: #1a1e27; border-radius: 3px; margin-top: 6px; overflow: hidden; display: none; }
  #progress-bar { height: 100%; background: #2f6df0; width: 0%; transition: width 0.3s ease; }
</style>
</head>
<body>
<header><b>ComfyUI Agent</b> — минимальный чат (M9) · session: <span id="sid"></span></header>
<div id="app">
  <div id="chat">
    <div id="log"></div>
    <div id="status"></div>
    <div id="progress-wrap"><div id="progress-bar"></div></div>
    <div id="controls">
      <input id="text" placeholder="например: сгенерируй фото кота" autofocus>
      <button id="suggest" title="Улучшить промпт">✨ Подсказка</button>
      <button id="send">Отправить</button>
    </div>
  </div>
  <div id="preview"><span class="sys">превью active_asset появится здесь</span></div>
</div>
<script>
const sid = localStorage.getItem('sid') || (Math.random().toString(36).slice(2) + Date.now().toString(36));
localStorage.setItem('sid', sid);
document.getElementById('sid').textContent = sid;
const log = document.getElementById('log');
const statusEl = document.getElementById('status');
const preview = document.getElementById('preview');
const progressWrap = document.getElementById('progress-wrap');
const progressBar = document.getElementById('progress-bar');

function addMsg(text, cls) {
  const d = document.createElement('div');
  d.className = 'msg ' + cls;
  d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}
function setStatus(t) { statusEl.textContent = t; }
function showPreview(url) {
  if (!url) return;
  preview.innerHTML = '';
  const img = new Image(); img.src = url; preview.appendChild(img);
}

const es = new EventSource('/events?session_id=' + encodeURIComponent(sid));
es.onmessage = (e) => {};
es.addEventListener('start', (e) => { const d = JSON.parse(e.data); addMsg('▶ ' + (d.request || d.capability), 'sys'); setStatus('запуск…'); });
es.addEventListener('status', (e) => {
  const d = JSON.parse(e.data);
  if (d.state === 'RUNNING') {
    setStatus('выполняется…');
    progressWrap.style.display = 'block';
    progressBar.style.width = '0%';
  } else {
    setStatus('состояние: ' + d.state);
  }
});
es.addEventListener('progress', (e) => {
  const d = JSON.parse(e.data);
  progressBar.style.width = d.pct + '%';
  setStatus('выполняется… ' + d.pct + '%');
});
es.addEventListener('result', (e) => {
  const d = JSON.parse(e.data);
  setStatus('готово: ' + d.state);
  progressWrap.style.display = 'none';
  progressBar.style.width = '0%';
  addMsg('✓ ' + d.active_workflow + ' → ' + d.active_asset, 'bot');
  if (d.preview) showPreview(d.preview);
});
es.addEventListener('error', (e) => {
  let msg = 'ошибка';
  try { msg = JSON.parse(e.data).error; } catch (_) {}
  addMsg('✗ ' + msg, 'bot'); setStatus('ошибка');
  progressWrap.style.display = 'none';
  progressBar.style.width = '0%';
});

async function send() {
  const text = document.getElementById('text').value.trim();
  if (!text) return;
  document.getElementById('text').value = '';
  addMsg(text, 'user');
  setStatus('отправка…');
  await fetch('/turn', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sid, request: text }),
  });
}
document.getElementById('send').addEventListener('click', send);
document.getElementById('text').addEventListener('keydown', (e) => { if (e.key === 'Enter') send(); });

// M11: ✨ Dynamic Prompt Suggestions (AD-32: original_preserved)
let suggestIndex = 0;
document.getElementById('suggest').addEventListener('click', async () => {
  const text = document.getElementById('text').value.trim();
  if (!text) return;
  try {
    const res = await fetch('/api/prompt/suggest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, index: suggestIndex }),
    });
    const data = await res.json();
    // AD-32: Не уничтожаем исходный текст, показываем подсказку
    addMsg('✨ Подсказка #' + data.variant_index + ': ' + data.enhanced_prompt, 'bot');
    suggestIndex = data.variant_index + 1;
  } catch (_) {
    addMsg('✗ Подсказка не удалась', 'bot');
  }
});

// восстановить active_asset при перезагрузке
fetch('/api/session?session_id=' + encodeURIComponent(sid))
  .then(r => r.json()).then(d => { if (d.active_asset) showPreview('/asset/' + d.active_asset); });
</script>
</body>
</html>
"""


def _make_handler(factory: ComfyUIServer):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # тихий лог
            return

        def _send_json(self, obj, code: int = 200) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _qs(self) -> dict:
            parsed = urllib.parse.urlparse(self.path)
            return urllib.parse.parse_qs(parsed.query)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            if path == "/" or path == "/index.html":
                self._send_html(_INDEX_HTML)
            elif path == "/events":
                self._handle_events(self._qs().get("session_id", [""])[0])
            elif path == "/api/session":
                sid = self._qs().get("session_id", [""])[0]
                self._send_json(factory.session_state(sid))
            elif path == "/api/feedback/history":
                sid = self._qs().get("session_id", [""])[0]
                self._send_json(factory.get_feedback_history(sid))
            elif path.startswith("/asset/"):
                self._handle_asset(path[len("/asset/"):])
            else:
                self._send_json({"error": "not found"}, code=404)

        def _send_html(self, content: str) -> None:
            data = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _handle_events(self, session_id: str) -> None:
            if not session_id:
                self._send_json({"error": "session_id required"}, code=400)
                return
            stream = factory.stream(session_id)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            idx = 0
            try:
                while True:
                    ev = stream.wait_next(idx)
                    if ev is None:
                        break
                    self.wfile.write(f"event: {ev.get('type')}\n".encode("utf-8"))
                    self.wfile.write(f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    idx += 1
                    if ev.get("type") in SessionStream.TERMINAL:
                        break
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _handle_asset(self, asset_id: str) -> None:
            if not asset_id:
                self._send_json({"error": "asset id required"}, code=400)
                return
            data, mime = factory.serve_asset(asset_id)
            if data is None:
                self._send_json({"error": "asset not found"}, code=404)
                return
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _handle_prompt_suggest(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0") or "0")
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw.decode("utf-8") or "{}")
            except (ValueError, json.JSONDecodeError):
                self._send_json({"error": "bad json"}, code=400)
                return

            text = body.get("text", "")
            idx = body.get("index", 0)
            
            # Context-aware (future M11.4: get from session)
            prompt_ctx = PromptContext(
                original_text=text,
                mode="suggestion",
                suggestion_index=idx,
            )
            result = factory.prompt_builder.build(prompt_ctx)
            
            self._send_json({
                "enhanced_prompt": result.enhanced_prompt,
                "original_preserved": result.original_preserved,
                "variant_index": result.variant_index,
                "source": result.source,
                "rationale": result.rationale,
            })

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/api/prompt/suggest":
                self._handle_prompt_suggest()
                return
            if parsed.path == "/api/feedback":
                self._handle_feedback()
                return
            if parsed.path != "/turn":
                self._send_json({"error": "not found"}, code=404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0") or "0")
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw.decode("utf-8") or "{}")
            except (ValueError, json.JSONDecodeError):
                self._send_json({"error": "bad json"}, code=400)
                return
            session_id = body.get("session_id") or "default"
            factory.run_turn(
                session_id,
                capability=body.get("capability"),
                request=body.get("request"),
                params=body.get("params"),
                assets=body.get("assets"),
            )
            self._send_json({"ok": True, "session_id": session_id})

        def _handle_feedback(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0") or "0")
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw.decode("utf-8") or "{}")
            except (ValueError, json.JSONDecodeError):
                self._send_json({"error": "bad json"}, code=400)
                return
            session_id = body.get("session_id")
            attempt_id = body.get("attempt_id")
            rating = body.get("rating")
            comment = body.get("comment", "")
            if not session_id or not attempt_id or rating is None:
                self._send_json({"error": "session_id, attempt_id, rating required"}, code=400)
                return
            result = factory.record_feedback(session_id, attempt_id, rating, comment)
            self._send_json(result)

    return Handler


def build_server(host: str = "127.0.0.1", port: int = 0, store: Optional[AssetStore] = None):
    """Создать ThreadingHTTPServer для M9 (store из env или data/assets)."""
    import os

    from app.registry.backends import BackendCatalog

    if store is None:
        root = os.environ.get("AGENT_ASSET_DIR")
        store = AssetStore(root=root)
    agent = ConversationAgent(store, backends=BackendCatalog.from_env())
    factory = ComfyUIServer(store, agent=agent)
    handler = _make_handler(factory)
    httpd = ThreadingHTTPServer((host, port), handler)
    return httpd, factory


def main() -> None:
    import os

    host = os.environ.get("AGENT_UI_HOST", "127.0.0.1")
    port = int(os.environ.get("AGENT_UI_PORT", "8189"))
    httpd, _ = build_server(host=host, port=port)
    url = f"http://{host}:{httpd.server_address[1]}"
    print(f"[M9 UI] serving on {url}  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
