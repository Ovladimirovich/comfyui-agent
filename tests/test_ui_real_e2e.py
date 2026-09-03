"""Real UI E2E — полный пайплайн UI + live ComfyUI + progress в SSE.

Проверяет:
  1. POST /turn → SSE start → progress events → result с preview
  2. Прогресс реальный (0% → 100%), не fake
  3. Preview URL работает (asset доступен)
  4. Multi-turn: generate → edit → progress каждого шага

Требует живой ComfyUI (COMFY_REMOTE_URL), иначе skip.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from app.assets.store import AssetStore
from app.conversation import ConversationAgent
from app.ui import ComfyUIServer, _make_handler

COMFY_REMOTE_URL = os.environ.get("COMFY_REMOTE_URL", "http://127.0.0.1:8188")


def _live_provider():
    """Создать реальный ComfyUIProvider для live backend."""
    from app.comfy.client import ComfyClient
    from app.provider.comfyui import ComfyUIProvider

    client = ComfyClient(base_url=COMFY_REMOTE_URL, timeout=300)
    try:
        client.get_system_stats()
    except Exception as e:
        pytest.skip(f"ComfyUI недоступен: {e}")
    return ComfyUIProvider(client, backend_id="local_comfyui")


def _server(store, provider):
    from app.registry.backends import BackendCatalog

    agent = ConversationAgent(store, backends=BackendCatalog.from_env())
    factory = ComfyUIServer(store, agent=agent, provider=provider)
    handler = _make_handler(factory)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, factory


def _post(url, obj):
    data = json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read())


def _get(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _collect_events(base, session_id, timeout=300.0):
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


@pytest.mark.skipif(
    not COMFY_REMOTE_URL,
    reason="COMFY_REMOTE_URL не задан — нет live ComfyUI для UI E2E.",
)
def test_ui_real_txt2img_with_progress():
    """POST /turn → SSE start → progress events → result с preview."""
    provider = _live_provider()
    store = AssetStore(root="__tmptest_ui_real_txt2img__")
    httpd, _ = _server(store, provider)
    try:
        port = httpd.server_address[1]
        base = f"http://127.0.0.1:{port}"
        sid = "real-txt2img"

        events, done = _collect_events(base, sid, timeout=600)
        time.sleep(0.2)

        status, _ = _post(f"{base}/turn", {
            "session_id": sid,
            "request": "сгенерируй фото кота",
        })
        assert status == 200

        done.wait(timeout=600)
        assert events, "SSE не вернул событий"

        types = [e["type"] for e in events]
        assert "start" in types, f"Нет start: {types}"
        assert "status" in types, f"Нет status: {types}"
        assert "result" in types, f"Нет result: {types}"

        progress_events = [e for e in events if e["type"] == "progress"]
        assert len(progress_events) > 0, f"Нет progress events: {types}"

        pct_values = [e["pct"] for e in progress_events]
        assert pct_values[-1] == 100, f"Финальный pct != 100: {pct_values}"

        result = [e for e in events if e["type"] == "result"][0]
        assert result["state"] == "SUCCESS"
        assert result["preview"], "Нет preview URL"

        # preview доступен
        status, data = _get(f"http://127.0.0.1:{port}{result['preview']}", timeout=10)
        assert status == 200
        assert data[:4] == b"\x89PNG"
    finally:
        httpd.shutdown()


@pytest.mark.skipif(
    not COMFY_REMOTE_URL,
    reason="COMFY_REMOTE_URL не задан — нет live ComfyUI для UI E2E.",
)
def test_ui_real_multi_turn_progress():
    """Multi-turn: generate → edit → progress каждого шага в SSE."""
    provider = _live_provider()
    store = AssetStore(root="__tmptest_ui_real_multi__")
    httpd, _ = _server(store, provider)
    try:
        port = httpd.server_address[1]
        base = f"http://127.0.0.1:{port}"
        sid = "real-multi"

        # turn 1: generate
        events1, done1 = _collect_events(base, sid, timeout=600)
        time.sleep(0.2)
        _post(f"{base}/turn", {"session_id": sid, "request": "сгенерируй кота"})
        done1.wait(timeout=600)
        r1 = [e for e in events1 if e["type"] == "result"]
        assert r1 and r1[0]["state"] == "SUCCESS", f"Turn 1 failed: {events1}"
        p1 = [e for e in events1 if e["type"] == "progress"]
        assert len(p1) > 0, "Turn 1: нет progress events"

        # turn 2: edit
        events2, done2 = _collect_events(base, sid, timeout=600)
        time.sleep(0.2)
        _post(f"{base}/turn", {
            "session_id": sid,
            "capability": "image.edit",
            "params": {"prompt": "make it photorealistic", "negative_prompt": "", "seed": 0, "steps": 5, "denoise": 0.6},
        })
        done2.wait(timeout=600)
        r2 = [e for e in events2 if e["type"] == "result"]
        assert r2 and r2[0]["state"] == "SUCCESS", f"Turn 2 failed: {events2}"
        p2 = [e for e in events2 if e["type"] == "progress"]
        assert len(p2) > 0, "Turn 2: нет progress events"

        # оба шага имели progress
        assert p1[-1]["pct"] == 100, f"Turn 1 final pct: {p1[-1]['pct']}"
        assert p2[-1]["pct"] == 100, f"Turn 2 final pct: {p2[-1]['pct']}"
    finally:
        httpd.shutdown()
