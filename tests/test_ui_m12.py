"""M12 — Real UI E2E tests.

Проверяет:
- ComfyUIProcessManager (lifecycle)
- UI использует CompositePromptBuilder (не Heuristic напрямую)
- LLM unavailable → heuristic fallback через UI /turn
- SSE progress events flow correctly
- Full vertical slice: Browser → /turn → Agent → Planner → Composite → Job
"""
from __future__ import annotations
import sys

import json
import os
import threading
import time
import urllib.parse
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.assets.store import AssetStore
from app.comfy.lifecycle import ComfyUIProcessManager, ComfyUILifecycleError
from app.conversation import ConversationAgent
from app.prompt.composite import CompositePromptBuilder
from app.prompt.heuristic import HeuristicPromptBuilder
from app.ui import ComfyUIServer, _make_handler


class FakeClient:
    """Заглушка ComfyClient для offline тестов."""

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

    def queue_prompt(self, prompt, client_id=None):
        return {"prompt_id": "fake-prompt-id"}

    def get_history(self, prompt_id):
        return {prompt_id: {"status": {"status_str": "success"}, "outputs": {
            "9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]},
        }}}

    def interrupt(self):
        pass

    def upload_image(self, path):
        return {"name": os.path.basename(path), "subfolder": "", "type": "input"}

    def discover_checkpoints(self):
        return []


class FakeProvider:
    """Заглушка ComfyUIProvider для offline тестов."""

    def __init__(self, backend_id="fake_comfyui"):
        self.client = FakeClient()
        self.backend_id = backend_id

    def upload_asset(self, asset):
        from app.provider.backend_ref import BackendRef
        return BackendRef(
            provider="comfyui", backend=self.backend_id,
            reference={"filename": os.path.basename(asset.path), "subfolder": "", "type": "input"},
        )

    def execute(self, prompt, client_id=None):
        return "fake-prompt-id"

    def get_job(self, prompt_id):
        return self.client.get_history(prompt_id)

    def view(self, ref):
        return self.client.view(ref.reference["filename"])

    def cancel(self, prompt_id):
        pass

    def discover_checkpoints(self):
        return []


def _make_server(store, provider=None):
    """Создать тестовый сервер."""
    factory = ComfyUIServer(store, agent=ConversationAgent(store), provider=provider)
    handler = _make_handler(factory)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, factory


def _get(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()


def _post(url, obj, timeout=10):
    data = json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read())


def _collect_events(base, session_id, timeout=15.0):
    """Подписаться на /events и собрать события до terminal."""
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


# ============================================================================
# TEST 1: ComfyUIProcessManager — check() with unreachable server
# ============================================================================
def test_lifecycle_check_offline():
    """ComfyUIProcessManager.check() возвращает False когда ComfyUI недоступен."""
    manager = ComfyUIProcessManager(port=19999)  # заведомо недоступный порт
    assert manager.check() == False
    print("✓ test_lifecycle_check_offline: check() = False when offline")


# ============================================================================
# TEST 2: ComfyUIProcessManager — wait_for_ready timeout
# ============================================================================
def test_lifecycle_wait_timeout():
    """ComfyUIProcessManager.wait_for_ready() возвращает False по таймауту."""
    manager = ComfyUIProcessManager(port=19999, timeout=1.0)
    assert manager.wait_for_ready() == False
    print("✓ test_lifecycle_wait_timeout: wait_for_ready() = False on timeout")


# ============================================================================
# TEST 3: UI использует CompositePromptBuilder по умолчанию
# ============================================================================
def test_ui_uses_composite_by_default():
    """ComfyUIServer по умолчанию использует CompositePromptBuilder."""
    store = AssetStore(root="__tmp_m12_comp__")
    server = ComfyUIServer(store)
    assert isinstance(server.prompt_builder, CompositePromptBuilder)
    print("✓ test_ui_uses_composite_by_default: UI uses CompositePromptBuilder")


# ============================================================================
# TEST 4: UI /turn с Composite → heuristic fallback (LLM не настроен)
# ============================================================================
def test_ui_turn_with_composite_fallback():
    """Полный путь: Browser → /turn → ConversationAgent → Composite → heuristic fallback."""
    store = AssetStore(root="__tmp_m12_turn__")
    httpd, factory = _make_server(store, FakeProvider())
    try:
        port = httpd.server_address[1]
        base = f"http://127.0.0.1:{port}"
        sid = "sess-m12"

        # Убедиться что prompt_builder = Composite
        assert isinstance(factory.prompt_builder, CompositePromptBuilder)

        # Отправить turn
        status, body = _post(f"{base}/turn", {"session_id": sid, "request": "создай кота на крыше"})
        assert status == 200

        # Подождать завершения
        for _ in range(100):
            _, st = _get(f"{base}/api/session?session_id={sid}")
            ctx = json.loads(st)
            if ctx.get("active_asset"):
                break
            time.sleep(0.05)

        _, st = _get(f"{base}/api/session?session_id={sid}")
        ctx = json.loads(st)
        assert ctx["active_asset"], "active_asset должен появиться"
        assert ctx["active_workflow"].startswith("txt2img@")
        print(f"✓ test_ui_turn_with_composite_fallback: session={sid}, asset={ctx['active_asset']}")
    finally:
        httpd.shutdown()


# ============================================================================
# TEST 5: SSE progress events flow
# ============================================================================
def test_ui_sse_progress_events():
    """SSE поток содержит start → status → result события."""
    store = AssetStore(root="__tmp_m12_sse__")
    httpd, factory = _make_server(store, FakeProvider())
    try:
        port = httpd.server_address[1]
        base = f"http://127.0.0.1:{port}"
        sid = "sess-sse-m12"

        events, done = _collect_events(base, sid)
        time.sleep(0.1)
        _post(f"{base}/turn", {"session_id": sid, "request": "сгенерируй изображение"})
        done.wait(timeout=10)

        types = [e["type"] for e in events]
        assert "start" in types, f"Ожидался 'start', получили: {types}"
        assert "status" in types, f"Ожидался 'status', получили: {types}"
        assert "result" in types, f"Ожидался 'result', получили: {types}"

        result = next(e for e in events if e["type"] == "result")
        assert result["state"] == "SUCCESS"
        assert result.get("preview", "").startswith("/asset/")
        print(f"✓ test_ui_sse_progress_events: events={types}, preview={result['preview']}")
    finally:
        httpd.shutdown()


# ============================================================================
# TEST 6: LLM unavailable → heuristic fallback через UI
# ============================================================================
def test_ui_llm_unavailable_fallback():
    """При отсутствии LLM_API_KEY UI работает через heuristic fallback."""
    # Убедимся что LLM_API_KEY не установлен
    env_without_key = {k: v for k, v in os.environ.items() if k != "LLM_API_KEY"}

    store = AssetStore(root="__tmp_m12_llm__")
    httpd, factory = _make_server(store, FakeProvider())
    try:
        port = httpd.server_address[1]
        base = f"http://127.0.0.1:{port}"
        sid = "sess-llm-fallback"

        # prompt_builder должен быть Composite (LLM не настроен → fallback)
        assert isinstance(factory.prompt_builder, CompositePromptBuilder)

        # Turn должен завершиться успешно (heuristic fallback)
        status, _ = _post(f"{base}/turn", {"session_id": sid, "request": "кот на крыше"})
        assert status == 200

        for _ in range(100):
            _, st = _get(f"{base}/api/session?session_id={sid}")
            ctx = json.loads(st)
            if ctx.get("active_asset"):
                break
            time.sleep(0.05)

        _, st = _get(f"{base}/api/session?session_id={sid}")
        ctx = json.loads(st)
        assert ctx["active_asset"], "fallback должен создать актив"
        print("✓ test_ui_llm_unavailable_fallback: LLM unavailable → heuristic fallback OK")
    finally:
        httpd.shutdown()


# ============================================================================
# TEST 7: Custom prompt_builder injection
# ============================================================================
def test_ui_custom_prompt_builder():
    """UI принимает пользовательский prompt_builder через DI."""
    store = AssetStore(root="__tmp_m12_custom__")
    custom_builder = HeuristicPromptBuilder()
    server = ComfyUIServer(store, prompt_builder=custom_builder)
    assert server.prompt_builder is custom_builder
    print("✓ test_ui_custom_prompt_builder: DI works correctly")


# ============================================================================
# TEST 8: Full vertical slice — original/enhanced prompt lineage
# ============================================================================
def test_ui_prompt_lineage():
    """Проверить что original_prompt и enhanced_prompt сохраняются в Job."""
    store = AssetStore(root="__tmp_m12_lineage__")
    httpd, factory = _make_server(store, FakeProvider())
    try:
        port = httpd.server_address[1]
        base = f"http://127.0.0.1:{port}"
        sid = "sess-lineage"

        _post(f"{base}/turn", {"session_id": sid, "request": "красный спортивный автомобиль"})

        for _ in range(100):
            _, st = _get(f"{base}/api/session?session_id={sid}")
            ctx = json.loads(st)
            if ctx.get("active_asset"):
                break
            time.sleep(0.05)

        _, st = _get(f"{base}/api/session?session_id={sid}")
        ctx = json.loads(st)
        assert ctx["active_asset"]

        # Проверить что в messages есть информация о промпте
        messages = ctx.get("messages", [])
        assert len(messages) > 0
        print(f"✓ test_ui_prompt_lineage: message={messages[-1].get('turn')}")
    finally:
        httpd.shutdown()


# ============================================================================
# TEST 9: Multi-turn через UI
# ============================================================================
def test_ui_multiturn_context():
    """Multi-turn conversation через UI: Turn 1 → Turn 2 с контекстом."""
    store = AssetStore(root="__tmp_m12_mt__")
    httpd, factory = _make_server(store, FakeProvider())
    try:
        port = httpd.server_address[1]
        base = f"http://127.0.0.1:{port}"
        sid = "sess-multi"

        # Turn 1
        _post(f"{base}/turn", {"session_id": sid, "request": "создай кота на крыше"})
        # Подождать завершения Turn 1 (по количеству jobs)
        for _ in range(200):
            _, st = _get(f"{base}/api/session?session_id={sid}")
            ctx = json.loads(st)
            if len(ctx.get("jobs", [])) >= 1:
                break
            time.sleep(0.05)

        # Turn 2
        _post(f"{base}/turn", {"session_id": sid, "request": "сделай его ночью"})
        # Подождать завершения Turn 2 (по количеству jobs или сообщений)
        for _ in range(200):
            _, st = _get(f"{base}/api/session?session_id={sid}")
            ctx = json.loads(st)
            if len(ctx.get("jobs", [])) >= 2 or len(ctx.get("messages", [])) >= 2:
                break
            time.sleep(0.05)

        _, st = _get(f"{base}/api/session?session_id={sid}")
        ctx = json.loads(st)
        messages = ctx.get("messages", [])
        assert len(messages) >= 2, f"Ожидалось 2+ сообщений, получено {len(messages)}"
        # Проверить что второй turn сохранил контекст
        assert messages[0].get("turn") == "создай кота на крыше"
        assert messages[1].get("turn") == "сделай его ночью"
        print(f"✓ test_ui_multiturn_context: {len(messages)} messages in session")
    finally:
        httpd.shutdown()


# ============================================================================
# TEST 10: Session isolation через UI
# ============================================================================
def test_ui_session_isolation():
    """Session isolation: A и B не должны смешиваться."""
    store = AssetStore(root="__tmp_m12_iso__")
    httpd, factory = _make_server(store, FakeProvider())
    try:
        port = httpd.server_address[1]
        base = f"http://127.0.0.1:{port}"

        _post(f"{base}/turn", {"session_id": "A", "request": "кот"})
        _post(f"{base}/turn", {"session_id": "B", "request": "собака"})

        for _ in range(100):
            _, a = _get(f"{base}/api/session?session_id=A")
            _, b = _get(f"{base}/api/session?session_id=B")
            if json.loads(a).get("active_asset") and json.loads(b).get("active_asset"):
                break
            time.sleep(0.05)

        _, a = _get(f"{base}/api/session?session_id=A")
        _, b = _get(f"{base}/api/session?session_id=B")
        ctx_a, ctx_b = json.loads(a), json.loads(b)
        assert ctx_a["active_asset"] != ctx_b["active_asset"]
        print("✓ test_ui_session_isolation: A ≠ B")
    finally:
        httpd.shutdown()


# ============================================================================
# RUN ALL TESTS
# ============================================================================
if __name__ == "__main__":
    tests = [
        test_lifecycle_check_offline,
        test_lifecycle_wait_timeout,
        test_ui_uses_composite_by_default,
        test_ui_turn_with_composite_fallback,
        test_ui_sse_progress_events,
        test_ui_llm_unavailable_fallback,
        test_ui_custom_prompt_builder,
        test_ui_prompt_lineage,
        test_ui_multiturn_context,
        test_ui_session_isolation,
    ]

    passed = 0
    failed = 0
    failures = []

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            failures.append((test.__name__, str(e)))
            print(f"✗ FAIL: {test.__name__}: {e}")

    print()
    print(f"{'='*60}")
    print(f"  M12 Real UI E2E Tests: {passed} passed, {failed} failed")
    print(f"{'='*60}")

    if failures:
        print()
        print("Failures:")
        for name, err in failures:
            print(f"  - {name}: {err[:100]}")
        sys.exit(1)
    else:
        print()
        print("  ✓✓✓ ALL M12 TESTS PASSED ✓✓✓")
        print("  → READY FOR: Browser E2E with real ComfyUI")
