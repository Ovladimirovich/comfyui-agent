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

import base64
import binascii
import html
import json
import mimetypes
import os
import tempfile
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from app.agent import _build_provider
from app.assets import AssetStore
from app.conversation import ConversationAgent, ConversationContext
from app.context.feedback import FeedbackRecord, FeedbackStore
from app.engine.experience import ExperienceStore
from app.prompt import CompositePromptBuilder, HeuristicPromptBuilder, PromptContext
from app.registry.runtime import discover_runtime


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
        knowledge_core=None,  # AD-48: KnowledgeCore (wired из build_server)
    ) -> None:
        self.store = store
        # M17/M24.1: feedback store — используем существующий у агента или создаём новый
        self.feedback_store = getattr(agent, "feedback_store", None) or FeedbackStore()
        # M25: experience store — хранит ChainExperience после завершения цепочек
        self.experience_store = getattr(agent, "experience_store", None) or ExperienceStore()
        self.agent = agent or ConversationAgent(
            store,
            feedback_store=self.feedback_store,
            experience_store=self.experience_store,
        )
        # M24.1: guarantee agent.feedback_store == self.feedback_store
        self.agent.feedback_store = self.feedback_store
        # M25: guarantee agent.experience_store == self.experience_store
        self.agent.experience_store = self.experience_store
        # AD-48: knowledge_core — единый источник knowledge для read-only endpoints
        # (приоритет явному аргументу; fallback на agent.knowledge_core для тестов)
        self.knowledge_core = knowledge_core or getattr(agent, "knowledge_core", None)
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

    def stream(self, session_id: str) -> SessionStream:
        with self._lock:
            return self.streams.setdefault(session_id, SessionStream())

    def job_status(self, prompt_id: str) -> Optional[dict]:
        """GET /api/jobs/{id} — статус Job из ExecutionHistory (runtime evidence).

        Детерминированный источник: ExecutionHistory.get_by_prompt_id() (M13).
        None → caller отвечает 404. runtime_graph отдаётся только из памяти
        (в JSONL не персистится на этом этапе, см. history.ExecutionRecord.to_dict).
        """
        history = getattr(self.agent, "execution_history", None)
        if history is None:
            return None
        rec = history.get_by_prompt_id(prompt_id)
        if rec is None:
            return None
        return {
            "prompt_id": rec.prompt_id,
            "capability": rec.capability,
            "workflow_id": rec.workflow_id,
            "workflow_version": rec.workflow_version,
            "state": rec.state,
            "attempt": rec.attempt,
            "duration": rec.duration,
            "error": rec.error_message,
            "error_class": rec.error_class,
            "output_assets": list(rec.output_assets or []),
            "backend_execution_identity": rec.backend_execution_identity,
            "chain_id": rec.chain_id,
            "chain_step_index": rec.chain_step_index,
            "params": dict(rec.params or {}),
            "runtime_graph": rec.runtime_graph,
        }

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
        if ws_timeout is None:  # explicit None from POST body -> original default
            ws_timeout = 15
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
                job_state = job.state.value if job is not None else None
                stream.push({
                    "type": "result",
                    "state": job_state,
                    "active_asset": ctx.active_asset,
                    "active_workflow": ctx.active_workflow,
                    "active_job": ctx.active_job,
                    "assets": sorted(ctx.assets),
                    "job": job.prompt_id if job is not None else None,
                    "error": getattr(job, "error", None) if job_state == "FAILED" else None,
                    "error_class": getattr(job, "error_class", None) if job_state == "FAILED" else None,
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

    # --- S9: POST /api/assets (multipart + JSON base64) ---

    def upload_asset(self, file_data: bytes, filename: str, mime=None):
        """Загрузить файл как Asset через AssetStore.ingest (S9)."""
        if not filename:
            raise ValueError("filename required")
        fd, tmp_path = tempfile.mkstemp(suffix=os.path.splitext(filename)[1])
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(file_data)
            asset_type = _mime_to_type(mime, filename)
            asset = self.store.ingest(
                tmp_path, type=asset_type,
                mime=mime or mimetypes.guess_type(filename)[0],
                role="input",
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        return {
            "asset_id": asset.id, "id": asset.id,
            "type": asset.type, "mime": asset.mime,
            "filename": filename, "size": len(file_data),
            "role": "input",
            "url": f"/asset/{asset.id}",
            "created_at": asset.created_at,
        }

    def upload_asset_multipart(self, raw: bytes, content_type: str) -> dict:
        """Обработать multipart: единственный file-part -> Asset (S9)."""
        boundary = None
        for token in content_type.split(";"):
            token = token.strip()
            if token.startswith("boundary="):
                boundary = token.split("=", 1)[1].strip('"')
        if not boundary:
            raise ValueError("missing multipart boundary")
        parts = _parse_multipart(raw, boundary)
        files = [p for p in parts if p["filename"]]
        if not files:
            raise ValueError("no file part in multipart body")
        if len(files) > 1:
            raise ValueError("multiple files not supported (S9: один asset на turn)")
        f = files[0]
        if not f["data"]:
            raise ValueError("empty file")
        return self.upload_asset(f["data"], f["filename"], f["content_type"])

    def cancel_job(self, prompt_id: str) -> Optional[dict]:
        """F1 §21: POST /api/jobs/{id}/cancel — реальный D-5A cancel (F4 реализация).

        Семантика (D-5A реализовано в F4):
        - неизвестный id → None → caller отвечает 404;
        - известный активный execution → реальная отмена через WorkflowEngine/ExecutionChain;
        - известный завершённый job → фактическое состояние из ExecutionHistory (не фейковый CANCELLED).
        """
        # F4: пробуем реальную отмену через активный execution
        cancel_result = self.agent.cancel_execution(prompt_id)
        if cancel_result is not None and "error" not in cancel_result:
            # Реальная отмена удалась
            return cancel_result

        # FALLBACK: job не найден как активный execution (уже завершён)
        status = self.job_status(prompt_id)
        if status is None:
            return None
        return {
            "id": prompt_id,
            "cancelled": False,
            "state": status["state"],
            "workflow_id": status["workflow_id"],
            "reason": "already_finished",
        }


def _parse_multipart(raw: bytes, boundary: str) -> list:
    """Разобрать multipart/form-data body на части (fields + files).

    Возвращает list[dict] с ключами: name, filename, content_type, data (bytes).
    """
    sep = boundary.encode("utf-8")
    parts = []
    for chunk in raw.split(b"--" + sep):
        if chunk.startswith(b"\r\n"):
            chunk = chunk[2:]
        if not chunk or chunk == b"--\r\n" or chunk == b"--":
            continue
        split = chunk.find(b"\r\n\r\n")
        if split < 0:
            continue
        headers_raw = chunk[:split].decode("utf-8", errors="replace")
        body = chunk[split + 4:]
        if body.endswith(b"\r\n"):
            body = body[:-2]
        meta = {}
        for line in headers_raw.split("\r\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip()
        cd = meta.get("content-disposition", "")
        name = ""
        filename = ""
        for part in cd.split(";"):
            part = part.strip()
            if part.startswith("name="):
                name = part.split("=", 1)[1].strip('"')
            elif part.startswith("filename="):
                filename = part.split("=", 1)[1].strip('"')
        parts.append({
            "name": name,
            "filename": filename,
            "content_type": meta.get("content-type", "application/octet-stream"),
            "data": body,
        })
    return parts


def _mime_to_type(mime, filename):
    """Определить media-agnostic Asset.type по mime/filename (S9: image)."""
    mime = mime or mimetypes.guess_type(filename)[0] or ""
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    return "input"


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
 es.addEventListener('chain_step', (e) => {
   const d = JSON.parse(e.data);
   const stepLabel = d.step + 1 + '/' + (d.total_steps || '?') + ': ' + (d.capability || '');
   addMsg('🔄 ' + stepLabel + ' [' + d.state + ']', 'sys');
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


def _node_brief(schema) -> dict:
    """Краткая сводка ноды для read-only API (AD-48). Работает и с NodeSchema,
    и с NodeFacts (у обоих есть class_type/display_name/category; выходные типы
    называются output_types у NodeSchema и outputs у NodeFacts)."""
    output_types = getattr(schema, "outputs", None) or getattr(schema, "output_types", ())
    return {
        "class_type": schema.class_type,
        "display_name": schema.display_name,
        "category": schema.category,
        "output_types": list(output_types),
    }


def knowledge_node_search(core, q: str, limit: int = 50) -> list[dict]:
    """Поиск нод по подстроке в class_type/display_name/category (read-only, S3)."""
    q_lower = q.lower().strip()
    if not q_lower:
        return []
    schemas = core.get_schemas()
    matched = [
        s for s in schemas.values()
        if q_lower in (s.class_type or "").lower()
        or q_lower in (s.display_name or "").lower()
        or q_lower in (s.category or "").lower()
    ]
    matched.sort(key=lambda s: s.class_type)
    return [_node_brief(s) for s in matched[:limit]]


def _package_facts_to_dict(pkg) -> dict:
    """Сериализация PackageFacts (frozen dataclass без собственного to_dict)."""
    return {
        "package_id": pkg.package_id,
        "classes": list(pkg.classes),
        "is_custom": pkg.is_custom,
        "api_family": pkg.api_family,
        "safety_profile": pkg.safety_profile,
        "doc_coverage": pkg.doc_coverage,
        "provenance": pkg.provenance,
    }


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
            elif path == "/api/nodes":
                self._handle_api_nodes()
            elif path == "/api/knowledge":
                self._handle_api_knowledge()
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
                    ev = stream.wait_next(idx, timeout=15)
                    if ev is None:
                        # keepalive ping during idle turn: idle >15s does not close SSE
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        continue
                    self.wfile.write(f"event: {ev.get('type')}\n".encode("utf-8"))
                    self.wfile.write(f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    idx += 1
                    if ev.get("type") in SessionStream.TERMINAL:
                        break
            except (BrokenPipeError, ConnectionResetError, TimeoutError, ConnectionAbortedError, OSError):
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
            if parsed.path == "/api/assets":
                self._handle_assets_upload()
                return
            if parsed.path == "/api/self-test":
                self._handle_api_self_test()
                return
            if parsed.path == "/api/chat":
                self._handle_chat()
                return
            if parsed.path != "/turn":
                self._send_json({"error": "not found"}, code=404)
                return
            body = self._read_json_body()
            if body is None:
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
        def _handle_assets_upload(self) -> None:
            """POST /api/assets -- file upload (PROJECT_SPEC §21, S9).

            Принимает multipart/form-data (единственный file-part) либо
            application/json {"data": base64, "name": ..., "type": ..., "mime": ...}.
            """
            content_type = self.headers.get("Content-Type", "")
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0:
                self._send_json({"error": "empty body"}, code=400)
                return
            if length > factory.store.max_upload_bytes:
                self._send_json({"error": "file too large"}, code=413)
                return
            if content_type.startswith("multipart/form-data"):
                raw = self.rfile.read(length)
                try:
                    result = factory.upload_asset_multipart(raw, content_type)
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, code=400)
                    return
            elif content_type.startswith("application/json"):
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw.decode("utf-8") or "{}")
                    data_b64 = payload.get("data")
                    if not data_b64:
                        raise ValueError("data (base64) required")
                    file_data = base64.b64decode(data_b64)
                    result = factory.upload_asset(
                        file_data,
                        payload.get("name", "file.bin"),
                        payload.get("mime"),
                    )
                except (ValueError, binascii.Error, json.JSONDecodeError) as exc:
                    self._send_json({"error": str(exc)}, code=400)
                    return
            else:
                self._send_json({"error": "multipart/form-data or application/json required"}, code=415)
                return
            self._send_json({"ok": True, **result})

        def _read_json_body(self):
            """Прочитать и распарсить JSON-тело POST; при ошибке -- 400 и None."""
            try:
                length = int(self.headers.get("Content-Length", "0") or "0")
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw.decode("utf-8") or "{}")
            except (ValueError, json.JSONDecodeError):
                self._send_json({"error": "bad json"}, code=400)
                return None
            return body

        def _handle_chat(self) -> None:
            """POST /api/chat -- §21 analog of /turn (requires request)."""
            body = self._read_json_body()
            if body is None:
                return
            session_id = body.get("session_id") or "default"
            request = body.get("request")
            if not request or not str(request).strip():
                self._send_json({"error": "request required"}, code=400)
                return
            factory.run_turn(
                session_id,
                capability=body.get("capability"),
                request=request,
                params=body.get("params"),
                assets=body.get("assets"),
            )
            self._send_json({"ok": True, "session_id": session_id, "endpoint": "/api/chat"})


            rating = body.get("rating")
            comment = body.get("comment", "")
            if not session_id or not attempt_id or rating is None:
                self._send_json({"error": "session_id, attempt_id, rating required"}, code=400)
                return
            result = factory.record_feedback(session_id, attempt_id, rating, comment)
            self._send_json(result)

        # ======================================================================
        # AD-48: read-only knowledge endpoints (S3/S6 → UI)
        # ======================================================================

        def _handle_api_nodes(self) -> None:
            """GET /api/nodes — поиск нод в KnowledgeCore (read-only, S3).

            Query params (все optional):
              node=<class_type>     — точный ответ по одной ноде (find_node)
              q=<substring>         — подстрока в class_type/display_name
              output=<TYPE>         — nodes_by_io(output_type=TYPE)
              package=<id>          — find_package (custom nodes)
            Без параметров — сводная статистика (stats).
            """
            core = getattr(factory, "knowledge_core", None)
            if core is None:
                self._send_json({"error": "knowledge not configured"}, code=503)
                return
            qs = self._qs()

            node = qs.get("node", [""])[0].strip()
            q = qs.get("q", [""])[0].strip()
            output_type = qs.get("output", [""])[0].strip().upper()
            package = qs.get("package", [""])[0].strip()

            try:
                if node:
                    facts = core.find_node(node)
                    if facts is None:
                        self._send_json({"error": f"node not found: {node}"}, code=404)
                        return
                    self._send_json({"node": facts.to_dict()})
                    return

                if package:
                    pkg = core.find_package(package)
                    if pkg is None:
                        self._send_json({"error": f"package not found: {package}"}, code=404)
                        return
                    self._send_json({"package": _package_facts_to_dict(pkg)})
                    return

                if q:
                    matches = knowledge_node_search(core, q)
                    self._send_json({"query": q, "count": len(matches), "nodes": matches})
                    return

                if output_type:
                    schemas = core.nodes_by_io(output_type=output_type)
                    matches = [
                        _node_brief(s) for s in schemas
                    ]
                    self._send_json({"output_type": output_type, "count": len(matches), "nodes": matches})
                    return

                # default: stats
                schemas = core.get_schemas()
                self._send_json({
                    "configured": True,
                    "stats": {
                        "schemas": len(schemas),
                        "candidates": len(core.get_candidates()),
                        "validated_nodes": len(core.get_validated_nodes()),
                    },
                })
            except Exception as exc:  # не ломать HTTP-слой из-за knowledge-ошибки
                self._send_json({"error": "knowledge query failed", "detail": str(exc)}, code=500)

        def _handle_api_knowledge(self) -> None:
            """GET /api/knowledge — explain_node / gap_report (read-only, S3).

            Query params:
              node=<class_type>     — подробное объяснение ноды (explain_node)
              gap=1                 — gap_report (чего не хватает до исполняемости)
            Без параметров — сводная статистика.
            """
            core = getattr(factory, "knowledge_core", None)
            if core is None:
                self._send_json({"error": "knowledge not configured"}, code=503)
                return
            qs = self._qs()

            node = qs.get("node", [""])[0].strip()
            want_gap = qs.get("gap", ["0"])[0].strip() in ("1", "true", "yes")

            try:
                if node:
                    explanation = core.explain_node(node)
                    if explanation is None:
                        self._send_json({"error": f"node not found: {node}"}, code=404)
                        return
                    self._send_json({"node": explanation.to_dict()})
                    return

                if want_gap:
                    gaps = [g.to_dict() for g in core.gap_report()]
                    self._send_json({"gaps": gaps, "count": len(gaps)})
                    return

                schemas = core.get_schemas()
                self._send_json({
                    "configured": True,
                    "stats": {
                        "schemas": len(schemas),
                        "candidates": len(core.get_candidates()),
                        "claims": len(core.get_claims()),
                        "confirmed_claims": len(core.get_confirmed_claims()),
                        "validated_nodes": len(core.get_validated_nodes()),
                    },
                })
            except Exception as exc:
                self._send_json({"error": "knowledge query failed", "detail": str(exc)}, code=500)

        def _handle_api_self_test(self):
            """POST /api/self-test — S6 self-test одной ноды (детерминированный gate).

            Body: {"node_class": str, "backend_id": str?, "base_url": str?}
            Делегирует в Agent.run_self_test (AD-47 консервативный gate).
            """
            body = self._read_json_body()
            if body is None or not isinstance(body, dict):
                self._send_json({"error": "bad json"}, code=400)
                return
            node_class = (body.get("node_class") or "").strip()
            if not node_class:
                self._send_json({"error": "node_class required"}, code=400)
                return
            backend_id = body.get("backend_id")
            base_url = body.get("base_url")
            try:
                result = factory.agent.run_self_test(
                    node_class,
                    backend_id=backend_id,
                    base_url=base_url,
                )
                self._send_json(result)
            except Exception as exc:
                self._send_json({"error": "self-test failed", "detail": str(exc)}, code=500)

    return Handler


def build_server(
    host: str = "127.0.0.1",
    port: int = 0,
    store: Optional[AssetStore] = None,
    knowledge_data_dir: Optional[str] = None,
):
    """Создать ThreadingHTTPServer для M9 (store из env или data/assets).

    AD-48: production-композиция — единственный composition root. Wiring:
      - KnowledgeCore строится из persistent snapshot (app/data/knowledge);
      - RuntimeValidator получает реальный transport (ComfyClient к default backend);
      - всё передаётся в ConversationAgent(knowledge_core=...).
    Fail-open (AD-45): если knowledge недоступен (load error) — сервер стартует
    как раньше, knowledge_core=None, без блокировки.

    knowledge_data_dir — seam для самодостаточных тестов: необязательный путь к
    snapshot'у knowledge. None (дефолт) = runtime-путь app/data/knowledge; production
    НЕ получает синтетические данные автоматически.
    """
    import os

    from app.registry.backends import BackendCatalog

    if store is None:
        root = os.environ.get("AGENT_ASSET_DIR")
        store = AssetStore(root=root)
    fb_store = FeedbackStore()
    exp_store = ExperienceStore()
    backends = backends_from_env()
    knowledge_core = _build_knowledge_core(backends=backends, data_dir=knowledge_data_dir)
    agent = ConversationAgent(
        store,
        backends=backends,
        feedback_store=fb_store,
        experience_store=exp_store,
        knowledge_core=knowledge_core,  # AD-48 wiring
    )
    factory = ComfyUIServer(store, agent=agent, knowledge_core=knowledge_core)
    handler = _make_handler(factory)
    httpd = ThreadingHTTPServer((host, port), handler)
    return httpd, factory


def backends_from_env():
    """BackendCatalog из env (инкапсуляция; один источник для server wiring).

    Вынесено отдельно, чтобы build_server и wiring knowledge использовали один
    и тот же список backend'ов (AD-48) — default backend задаёт transport.
    """
    from app.registry.backends import BackendCatalog

    return BackendCatalog.from_env()


def _build_knowledge_core(backends=None, data_dir: Optional[str] = None):
    """AD-48: построить KnowledgeCore с RuntimeValidator (реальный transport).

    Args:
        backends: BackendCatalog — первый backend задаёт transport;
        data_dir: необязательный путь к snapshot'у knowledge. None (дефолт) —
            runtime-путь app/data/knowledge: production использует только
            реальный snapshot и НЕ получает синтетические данные. Параметр —
            исключительно seam для самодостаточных тестов.

    Возвращает KnowledgeCore или None при ошибке (fail-open, AD-45). Self-test
    (S6) использует тот же RuntimeValidator → консервативный gate (AD-47).
    """
    try:
        from app.comfy.client import ComfyClient
        from app.knowledge.core import KnowledgeCore
        from app.knowledge.runtime_validator import RuntimeValidator

        base_url = None
        if backends is not None and backends.backends:
            base_url = backends.backends[0].base_url
        validator = RuntimeValidator(comfy_client=ComfyClient(base_url=base_url))
        return KnowledgeCore(runtime_validator=validator, data_dir=data_dir)
    except Exception:
        # fail-open: knowledge отсутствие != capability absence (AD-45)
        return None


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
