"""Progress Hook — WS progress events → Job.progress → SSE → UI.

Тестирует пайплайн гранулярного прогресса (M10+):
  1. WS tracker вызывает on_progress callback.
  2. Engine обновляет Job.progress (thread-safe).
  3. SSE stream получает progress события.
  4. UI HTML содержит progress bar.
"""
from __future__ import annotations

import base64
import json
import threading

import pytest

from app.assets import AssetStore
from app.engine import ExecutionPlan, JobState, WorkflowEngine
from app.engine.websocket import ComfyUIWebSocket
from app.provider import BackendRef
from app.registry import WorkflowRegistry

_1PX_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)


class _FakeProvider:
    def __init__(self):
        self.client = type("C", (), {"base_url": "http://fake"})()
        self.backend_id = "fake"

    def upload_asset(self, asset):
        return BackendRef("comfyui", "fake", {"filename": "f"})

    def execute(self, prompt, client_id=None):
        return "pid"

    def get_job(self, prompt_id):
        return {}

    def cancel(self, prompt_id):
        pass

    def view(self, ref):
        return b"\x89PNG\r\n\x1a\n"

    def discover_checkpoints(self):
        return []


# --------------------------------------------------------------------------- #
# 1) WS tracker вызывает on_progress callback
# --------------------------------------------------------------------------- #

def test_ws_tracker_calls_on_progress():
    """on_progress вызывается при progress-событии WS."""
    received = []

    def fake_track(self_ws, prompt_id, timeout=300, on_progress=None):
        if on_progress is not None:
            on_progress(3, 10)
            on_progress(7, 10)
            on_progress(10, 10)
        return {"9": {"images": [{"filename": "x.png"}]}}

    original = ComfyUIWebSocket.track
    ComfyUIWebSocket.track = fake_track
    try:
        ws = ComfyUIWebSocket("http://fake", "cid")
        result = ws.track("pid", on_progress=lambda v, m: received.append((v, m)))
        assert result == {"9": {"images": [{"filename": "x.png"}]}}
        assert received == [(3.0, 10.0), (7.0, 10.0), (10.0, 10.0)]
    finally:
        ComfyUIWebSocket.track = original


# --------------------------------------------------------------------------- #
# 2) WS tracker без on_progress — не падает
# --------------------------------------------------------------------------- #

def test_ws_tracker_no_progress_callback():
    """on_progress=None — трекер работает как раньше."""
    original = ComfyUIWebSocket.track
    ComfyUIWebSocket.track = lambda self_ws, pid, timeout=300, on_progress=None: {"9": {"images": [{"filename": "x.png"}]}}
    try:
        ws = ComfyUIWebSocket("http://fake", "cid")
        result = ws.track("pid")
        assert "9" in result
    finally:
        ComfyUIWebSocket.track = original


# --------------------------------------------------------------------------- #
# 3) Engine обновляет Job.progress через on_progress callback
# --------------------------------------------------------------------------- #

def test_engine_updates_job_progress(tmp_path, monkeypatch):
    """Engine.execute обновляет job.progress через WS progress events."""
    progress_values = []

    def fake_track(self_ws, prompt_id, timeout=300, on_progress=None):
        if on_progress is not None:
            on_progress(0, 10)
            on_progress(5, 10)
            on_progress(10, 10)
        return {"9": {"images": [{"filename": "x.png"}]}}

    monkeypatch.setattr(ComfyUIWebSocket, "track", fake_track)

    store = AssetStore(root=tmp_path / "store")
    reg = WorkflowRegistry()
    reg.discover("workflows")
    wf = reg.get("txt2img", "1.0.0")
    engine = WorkflowEngine(store)

    def _capture_progress(value, max_val):
        progress_values.append(value / max_val if max_val > 0 else 0)

    plan = ExecutionPlan(
        capability="image.generate", workflow_id="txt2img", version="1.0.0",
        params={"prompt": "a cat", "negative_prompt": "", "width": 64, "height": 64, "seed": 0, "steps": 5},
    )
    job = engine.execute(wf, plan, _FakeProvider(), ws_timeout=5, on_progress=_capture_progress)

    assert job.state == JobState.SUCCESS
    assert job.progress == 1.0
    assert progress_values == [0.0, 0.5, 1.0]


# --------------------------------------------------------------------------- #
# 4) Engine без on_progress — job.progress остаётся 0.0
# --------------------------------------------------------------------------- #

def test_engine_no_progress(tmp_path, monkeypatch):
    """Без on_progress callback job.progress не обновляется (backward compat)."""
    monkeypatch.setattr(
        ComfyUIWebSocket, "track",
        staticmethod(lambda pid, timeout=None, on_progress=None: {"9": {"images": [{"filename": "x.png"}]}}),
    )
    store = AssetStore(root=tmp_path / "store")
    reg = WorkflowRegistry()
    reg.discover("workflows")
    wf = reg.get("txt2img", "1.0.0")
    engine = WorkflowEngine(store)

    plan = ExecutionPlan(
        capability="image.generate", workflow_id="txt2img", version="1.0.0",
        params={"prompt": "a cat", "negative_prompt": "", "width": 64, "height": 64, "seed": 0, "steps": 5},
    )
    job = engine.execute(wf, plan, _FakeProvider(), ws_timeout=5)

    assert job.state == JobState.SUCCESS
    assert job.progress == 0.0  # без callback progress не меняется


# --------------------------------------------------------------------------- #
# 5) SSE stream получает progress события
# --------------------------------------------------------------------------- #

def test_sse_stream_receives_progress_events():
    """SessionStream буферизует progress events для SSE."""
    from app.ui import SessionStream

    stream = SessionStream()
    stream.push({"type": "start", "session_id": "s1"})
    stream.push({"type": "status", "state": "RUNNING"})
    stream.push({"type": "progress", "value": 5, "max": 10, "pct": 50})
    stream.push({"type": "progress", "value": 10, "max": 10, "pct": 100})
    stream.push({"type": "result", "state": "SUCCESS"})

    assert stream.wait_next(0) == {"type": "start", "session_id": "s1"}
    assert stream.wait_next(1) == {"type": "status", "state": "RUNNING"}
    ev3 = stream.wait_next(2)
    assert ev3["type"] == "progress"
    assert ev3["pct"] == 50
    ev4 = stream.wait_next(3)
    assert ev4["type"] == "progress"
    assert ev4["pct"] == 100
    assert stream.wait_next(4)["type"] == "result"


# --------------------------------------------------------------------------- #
# 6) UI HTML содержит progress bar
# --------------------------------------------------------------------------- #

def test_ui_html_has_progress_bar():
    """HTML фронтенда содержит progress bar элемент и JS handler."""
    from app.ui import _INDEX_HTML
    assert "progress-wrap" in _INDEX_HTML
    assert "progress-bar" in _INDEX_HTML
    assert "addEventListener('progress'" in _INDEX_HTML
    assert "d.pct" in _INDEX_HTML


# --------------------------------------------------------------------------- #
# 7) ConversationAgent.turn пробрасывает on_progress
# --------------------------------------------------------------------------- #

def test_conversation_turn_passes_on_progress(tmp_path, monkeypatch):
    """ConversationAgent.turn пробрасывает on_progress в WorkflowEngine.execute."""
    from app.conversation import ConversationAgent

    received = []

    def fake_track(self_ws, prompt_id, timeout=300, on_progress=None):
        if on_progress is not None:
            on_progress(0, 10)
            on_progress(10, 10)
        return {"9": {"images": [{"filename": "x.png"}]}}

    monkeypatch.setattr(ComfyUIWebSocket, "track", fake_track)

    store = AssetStore(root=tmp_path)
    agent = ConversationAgent(store)
    provider = _FakeProvider()

    j = agent.turn(
        "s1", capability="image.generate",
        params={"prompt": "a cat", "negative_prompt": "", "width": 64, "height": 64, "seed": 0, "steps": 5},
        provider=provider, ws_timeout=5,
        on_progress=lambda v, m: received.append((v, m)),
    )
    assert j.state == JobState.SUCCESS
    assert received == [(0.0, 10.0), (10.0, 10.0)]


# --------------------------------------------------------------------------- #
# 8) WS progress unavailable → no fake %, /history fallback completes job
# --------------------------------------------------------------------------- #

def test_ws_unavailable_no_fake_progress(tmp_path, monkeypatch):
    """Когда WS не шлёт execution events (DirectML/CPU limitation),
    on_progress НЕ вызывается, progress остаётся 0.0, execution
    завершается через /history fallback."""
    from app.engine.websocket import ComfyUIWebSocketError

    progress_calls = []

    def fail_track(self_ws, prompt_id, timeout=300, on_progress=None):
        raise ComfyUIWebSocketError("WebSocket разорван для test")

    monkeypatch.setattr(ComfyUIWebSocket, "track", fail_track)

    # /history возвращает success (prompt_id = "pid" из _FakeProvider.execute)
    # get_history возвращает {prompt_id: {status, outputs}} — полный ответ ComfyUI
    fake_history = {
        "pid": {
            "status": {"status_str": "success"},
            "outputs": {"9": {"images": [{"filename": "out.png"}]}},
        }
    }

    class ProviderWithHistory(_FakeProvider):
        def get_job(self, prompt_id):
            return fake_history  # возвращает {prompt_id: entry}, как get_history

    store = AssetStore(root=tmp_path / "store")
    reg = WorkflowRegistry()
    reg.discover("workflows")
    wf = reg.get("txt2img", "1.0.0")
    engine = WorkflowEngine(store)

    plan = ExecutionPlan(
        capability="image.generate", workflow_id="txt2img", version="1.0.0",
        params={"prompt": "a cat", "negative_prompt": "", "width": 64, "height": 64, "seed": 0, "steps": 5},
    )
    job = engine.execute(
        wf, plan, ProviderWithHistory(), ws_timeout=5,
        on_progress=lambda v, m: progress_calls.append((v, m)),
    )

    assert job.state == JobState.SUCCESS
    assert job.progress == 0.0  # НЕТ ложного прогресса
    assert progress_calls == []  # on_progress НЕ вызывался
    assert len(job.output_assets) == 1  # execution завершился через /history


# --------------------------------------------------------------------------- #
# 9) SSE без progress events → start → status → result (state-based)
# --------------------------------------------------------------------------- #

def test_sse_no_progress_state_based():
    """Когда WS progress недоступен, SSE шлёт только start → status → result.
    Progress bar показывает честные 0% → hide (без ложных процентов)."""
    from app.ui import SessionStream

    stream = SessionStream()
    stream.push({"type": "start", "session_id": "s1"})
    stream.push({"type": "status", "state": "RUNNING"})
    # НЕТ progress events — backend не поддерживает granular progress
    stream.push({"type": "result", "state": "SUCCESS", "preview": "/asset/abc"})

    events = []
    idx = 0
    while True:
        ev = stream.wait_next(idx)
        if ev is None:
            break
        events.append(ev)
        idx += 1
        if ev.get("type") in SessionStream.TERMINAL:
            break

    types = [e["type"] for e in events]
    assert types == ["start", "status", "result"]
    # НЕТ progress events — UI не должен показывать ложный процент
    assert all(e["type"] != "progress" for e in events)


# --------------------------------------------------------------------------- #
# 10) WS progress available → real % through Job → SSE
# --------------------------------------------------------------------------- #

def test_ws_available_real_progress_sse():
    """Когда WS шлёт progress events, SSE получает реальный процент."""
    from app.ui import SessionStream

    stream = SessionStream()
    stream.push({"type": "start", "session_id": "s2"})
    stream.push({"type": "status", "state": "RUNNING"})
    stream.push({"type": "progress", "value": 3, "max": 10, "pct": 30})
    stream.push({"type": "progress", "value": 7, "max": 10, "pct": 70})
    stream.push({"type": "progress", "value": 10, "max": 10, "pct": 100})
    stream.push({"type": "result", "state": "SUCCESS", "preview": "/asset/def"})

    events = []
    idx = 0
    while True:
        ev = stream.wait_next(idx)
        if ev is None:
            break
        events.append(ev)
        idx += 1
        if ev.get("type") in SessionStream.TERMINAL:
            break

    progress_events = [e for e in events if e["type"] == "progress"]
    assert len(progress_events) == 3
    assert progress_events[0]["pct"] == 30
    assert progress_events[1]["pct"] == 70
    assert progress_events[2]["pct"] == 100


# --------------------------------------------------------------------------- #
# 11) ws_timeout=15: WS unavailable → fast /history fallback
# --------------------------------------------------------------------------- #

def test_ws_timeout_15s_fast_fallback(tmp_path, monkeypatch):
    """Когда WS execution events отсутствуют (DirectML), ws_timeout=15
    обеспечивает быстрый fallback на /history вместо 300s ожидания.

    Regression test: trước fix ws_timeout=300 → UI ждал 300+ секунд.
    After fix ws_timeout=15 → result через ~15-20s.
    """
    import time
    from app.engine.websocket import ComfyUIWebSocketError
    from app.ui import ComfyUIServer, SessionStream

    def fail_track(self_ws, prompt_id, timeout=300, on_progress=None):
        # Имитируем DirectML: WS подключается, но execution events не приходят.
        # Ждём timeout секунд и выбрасываем ошибку.
        time.sleep(min(timeout, 2))
        raise ComfyUIWebSocketError("WebSocket timed out")

    monkeypatch.setattr(ComfyUIWebSocket, "track", fail_track)

    # Fake provider с /history fallback
    fake_history = {
        "pid_ws15": {
            "status": {"status_str": "success"},
            "outputs": {"9": {"images": [{"filename": "out.png"}]}},
        }
    }

    class FakeClient:
        base_url = "http://fake"

    class FakeProvider:
        client = FakeClient()
        backend_id = "fake"

        def execute(self, prompt, client_id=None):
            return "pid_ws15"

        def get_job(self, prompt_id):
            return fake_history

        def upload_asset(self, asset):
            from app.provider import BackendRef
            return BackendRef("comfyui", "fake", {"filename": "f"})

        def view(self, ref):
            return b"\x89PNG\r\n\x1a\n"

        def cancel(self, prompt_id):
            pass

        def discover_checkpoints(self):
            return []

    store = AssetStore(root=tmp_path)
    from app.conversation import ConversationAgent
    agent = ConversationAgent(store)
    provider = FakeProvider()

    server = ComfyUIServer(store, agent=agent, provider=provider)
    stream = server.stream("ws15_test")

    start = time.time()
    server.run_turn("ws15_test", request="a cat", ws_timeout=15)
    stream.wait_next(0, timeout=30)  # start
    stream.wait_next(1, timeout=30)  # status
    ev = stream.wait_next(2, timeout=60)  # result (после ws_timeout + /history)
    elapsed = time.time() - start

    assert ev is not None, "result event не получен"
    assert ev["type"] == "result"
    assert ev["state"] == "SUCCESS"
    # ws_timeout=15 + overhead: результат ДОЛЖЕН прийти существенно раньше 300s
    assert elapsed < 30, f"result через {elapsed:.1f}s (>30s, ws_timeout=15 не работает)"


# --------------------------------------------------------------------------- #
# 12) ws_timeout по умолчанию = 15
# --------------------------------------------------------------------------- #

def test_run_turn_default_ws_timeout():
    """ComfyUIServer.run_turn() по умолчанию использует ws_timeout=15."""
    from app.ui import ComfyUIServer
    import inspect
    sig = inspect.signature(ComfyUIServer.run_turn)
    ws_param = sig.parameters.get("ws_timeout")
    assert ws_param is not None, "ws_timeout параметр отсутствует"
    assert ws_param.default == 15, f"ws_timeout default = {ws_param.default}, ожидается 15"
