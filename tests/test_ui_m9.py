"""M9 UI (минимальный чат + preview + progress SSE) — offline, без реального ComfyUI.

Использует FakeProvider/FakeClient (как test_agent.py), чтобы поднять ComfyUIServer
и проверить: отдачу страницы, запуск turn через ConversationAgent, SSE-поток событий,
preview ассета и изоляцию session. Без mock-success: реальный execution-core путь
(Agent.prepare → resolve_asset_inputs → WorkflowEngine.execute) с fake backend.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

from app.assets.store import AssetStore
from app.assets.types import Asset
from app.conversation import ConversationAgent
from app.ui import ComfyUIServer, _make_handler


class FakeClient:
    def __init__(self, base_url="http://127.0.0.1:9999"):
        self.base_url = base_url

    def get_system_stats(self):
        raise RuntimeError("offline fake client")

    def get_object_info(self):
        return {}

    def view(self, filename, subfolder="", type_="output"):
        if filename.endswith(".wav"):
            return b"RIFF\x00\x00\x00\x00WAVEfmt "
        return b"\x89PNG\r\n\x1a\n"


class FakeProvider:
    def __init__(self, backend_id="fake_comfyui"):
        self.client = FakeClient()
        self.backend_id = backend_id

    def upload_asset(self, asset):
        from app.provider.backend_ref import BackendRef
        return BackendRef(
            provider="comfyui", backend=self.backend_id,
            reference={"filename": asset.path.split("/")[-1], "subfolder": "", "type": "input"},
        )

    def execute(self, prompt, client_id=None):
        return "fake-prompt-id"

    def get_job(self, prompt_id):
        return {prompt_id: {"status": {"status_str": "success"}, "outputs": {
            "9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]},
        }}}

    def view(self, ref):
        return self.client.view(ref.reference["filename"])

    def cancel(self, prompt_id):
        pass

    def discover_checkpoints(self):
        return []


def _server(store, provider):
    factory = ComfyUIServer(store, agent=ConversationAgent(store), provider=provider)
    handler = _make_handler(factory)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, factory


def _get(url):
    import urllib.error

    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _post(url, obj):
    data = json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read())


def _collect_events(base, session_id, timeout=10.0):
    """Подписаться на /events и собрать события до terminal (result/error)."""
    url = f"{base}/events?session_id={urllib.parse.quote(session_id)}"
    events = []
    done = threading.Event()

    def reader():
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                for raw in r:
                    line = raw.decode("utf-8")
                    if line.startswith("data:"):
                        ev = json.loads(line[5:].strip())
                        events.append(ev)
                        if ev.get("type") in ("result", "error"):
                            done.set()
                            break
        except Exception:
            done.set()

    th = threading.Thread(target=reader, daemon=True)
    th.start()
    return events, done


def test_ui_serves_index():
    store = AssetStore(root="__tmptest_ui_index__")
    httpd, _ = _server(store, FakeProvider())
    try:
        port = httpd.server_address[1]
        status, body = _get(f"http://127.0.0.1:{port}/")
        assert status == 200
        text = body.decode("utf-8")
        assert "<!doctype html>" in text.lower()
        assert "chat" in text.lower()
    finally:
        httpd.shutdown()


def test_ui_turn_creates_asset_and_preview():
    store = AssetStore(root="__tmptest_ui_turn__")
    httpd, _ = _server(store, FakeProvider())
    try:
        port = httpd.server_address[1]
        base = f"http://127.0.0.1:{port}"
        sid = "sess-turn"
        status, _ = _post(f"{base}/turn", {"session_id": sid, "request": "сделай фото кота"})
        assert status == 200
        # дождаться завершения turn
        for _ in range(50):
            _, st = _get(f"{base}/api/session?session_id={sid}")
            if json.loads(st).get("active_asset"):
                break
            time.sleep(0.05)
        _, st = _get(f"{base}/api/session?session_id={sid}")
        ctx = json.loads(st)
        assert ctx["active_asset"], "active_asset должен появиться"
        assert ctx["active_workflow"].startswith("txt2img@")
        aid = ctx["active_asset"]
        status, data = _get(f"{base}/asset/{aid}")
        assert status == 200
        assert data[:4] == b"\x89PNG"
    finally:
        httpd.shutdown()


def test_ui_sse_streams_start_and_result():
    store = AssetStore(root="__tmptest_ui_sse__")
    httpd, _ = _server(store, FakeProvider())
    try:
        port = httpd.server_address[1]
        base = f"http://127.0.0.1:{port}"
        sid = "sess-sse"
        events, done = _collect_events(base, sid)
        time.sleep(0.1)  # дать SSE-хендлеру подписаться
        _post(f"{base}/turn", {"session_id": sid, "request": "сгенерируй изображение"})
        done.wait(timeout=10)
        types = [e["type"] for e in events]
        assert "start" in types, events
        assert "status" in types, events
        assert "result" in types, events
        result = [e for e in events if e["type"] == "result"][0]
        assert result["state"] == "SUCCESS"
        assert result["preview"].startswith("/asset/")
    finally:
        httpd.shutdown()


def test_ui_session_isolation():
    store = AssetStore(root="__tmptest_ui_iso__")
    httpd, _ = _server(store, FakeProvider())
    try:
        port = httpd.server_address[1]
        base = f"http://127.0.0.1:{port}"
        _post(f"{base}/turn", {"session_id": "A", "request": "фото кота"})
        _post(f"{base}/turn", {"session_id": "B", "request": "видео океана"})
        for _ in range(50):
            _, a = _get(f"{base}/api/session?session_id=A")
            _, b = _get(f"{base}/api/session?session_id=B")
            if json.loads(a).get("active_asset") and json.loads(b).get("active_asset"):
                break
            time.sleep(0.05)
        _, a = _get(f"{base}/api/session?session_id=A")
        _, b = _get(f"{base}/api/session?session_id=B")
        a, b = json.loads(a), json.loads(b)
        assert a["active_asset"] != b["active_asset"]
        assert a["active_asset"] not in b["assets"]
        assert b["active_asset"] not in a["assets"]
    finally:
        httpd.shutdown()


def test_ui_asset_404():
    store = AssetStore(root="__tmptest_ui_404__")
    httpd, _ = _server(store, FakeProvider())
    try:
        port = httpd.server_address[1]
        status, _ = _get(f"http://127.0.0.1:{port}/asset/does-not-exist")
        assert status == 404
    finally:
        httpd.shutdown()
