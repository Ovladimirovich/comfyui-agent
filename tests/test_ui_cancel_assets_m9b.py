"""D-5A cancel + /api/assets — offline-тесты нового поведения в ComfyUIServer.

Проверяет через HTTP-контракт:
  1. POST /api/assets — загрузка ассета (multipart + JSON base64), лимиты размера.
  2. POST /api/jobs/{id}/cancel — отмена job (404 для неизвестного, 409 для terminal).
  3. Мягкая отмена живого turn через session_id (cancel_session → cancel_check).

И unit-уровень retry-boundary отмены через ConversationAgent.turn
с инжектированным failing semantic verifier (retryable 'verification').

Без реального ComfyUI: FakeProvider (как test_ui_m9.py). Offline и детерминированно.
"""
from __future__ import annotations

import base64
import io
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.server import ThreadingHTTPServer

from app.assets.store import AssetStore
from app.conversation import ConversationAgent
from app.engine.retry import RetryPolicy
from app.ui import ComfyUIServer, _make_handler


# --- фейковый verifier, который всегда ПРОВАЛИВАЕТ semantic (score 0.1) ---
@dataclass
class _FailingSemVerResult:
    score: float = 0.1
    matches_intent: bool = False
    issues: list = None
    suggested_params: dict = None
    raw_response: str = None
    error: str = None

    def __post_init__(self):
        self.issues = self.issues or ["fake failing verification"]

    @property
    def ok(self) -> bool:
        return False


class _FailingSemVerifier:
    """Vision-verifier максимум: score 0.1, error=None → retryable 'verification'."""
    def verify(self, request, output_path, capability="image.generate",
               previous_output_path=None):
        return _FailingSemVerResult(error=None)


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
        # отдаём выхлоп и для node "9" (txt2img/upscale), и для node "2" (pollinations/other)
        return {prompt_id: {"status": {"status_str": "success"}, "outputs": {
            "9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]},
            "2": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]},
        }}}

    def view(self, ref):
        return self.client.view(ref.reference["filename"])

    def cancel(self, prompt_id):
        pass

    def discover_checkpoints(self):
        return []


def _server(store, provider=None, agent=None):
    factory = ComfyUIServer(store, agent=agent, provider=provider or FakeProvider())
    handler = _make_handler(factory)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, factory


def _port(httpd):
    return httpd.server_address[1]


def _get(url):
    import urllib.error
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _post_json(url, obj):
    data = json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


# --- /api/assets: multipart ---
def test_upload_asset_multipart():
    store = AssetStore(root="__tmp_assets_mp__")
    httpd, _ = _server(store)
    try:
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        boundary = "X-BOUNDARY-123"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="img.png"\r\n'
            "Content-Type: image/png\r\n\r\n"
        ).encode("utf-8") + png + (
            f"\r\n--{boundary}\r\n"
            'Content-Disposition: form-data; name="role"\r\n\r\n'
            "input\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{_port(httpd)}/api/assets",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            status = r.status
            result = json.loads(r.read())
        assert status == 200
        assert result.get("asset_id")
        assert result.get("type") == "image"
        assert result.get("role") == "input"
        # ассет существует в store
        asset = store.get(result["asset_id"])
        assert asset is not None
    finally:
        httpd.shutdown()


# --- /api/assets: JSON base64 ---
def test_upload_asset_json_base64():
    store = AssetStore(root="__tmp_assets_json__")
    httpd, _ = _server(store)
    try:
        payload = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16).decode("ascii")
        status, result = _post_json(
            f"http://127.0.0.1:{_port(httpd)}/api/assets",
            {"data": payload, "name": "pic.png", "type": "image", "role": "input"},
        )
        assert status == 200
        assert result.get("asset_id")
        assert result.get("type") == "image"
        # preview отдаётся
        code, _ = _get(f"http://127.0.0.1:{_port(httpd)}/asset/{result['asset_id']}")
        assert code == 200
    finally:
        httpd.shutdown()


# --- /api/assets: лимит размера (413) ---
def test_upload_asset_too_large():
    store = AssetStore(root="__tmp_assets_big__", max_upload_bytes=32)
    httpd, _ = _server(store)
    try:
        body = b"\x00" * 100
        payload = base64.b64encode(body).decode("ascii")
        data = json.dumps({"data": payload, "name": "big.bin"}).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{_port(httpd)}/api/assets", data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=10)
            assert False, "ожидали 413"
        except urllib.error.HTTPError as e:
            assert e.code == 413
    finally:
        httpd.shutdown()


# --- /api/jobs/{id}/cancel: неизвестный job (без session_id) → 404 ---
def test_cancel_unknown_job_404():
    store = AssetStore(root="__tmp_cancel_404__")
    httpd, _ = _server(store)
    try:
        status, body = _post_json(
            f"http://127.0.0.1:{_port(httpd)}/api/jobs/does-not-exist/cancel", {}
        )
        assert status == 404, (status, body)
        assert "not found" in body.get("error", "")
    finally:
        httpd.shutdown()


# --- /api/jobs/{id}/cancel: мягкая отмена с session_id без активного turn → 409 ---
def test_cancel_no_active_turn_409():
    store = AssetStore(root="__tmp_cancel_noActive__")
    httpd, _ = _server(store)
    try:
        status, body = _post_json(
            f"http://127.0.0.1:{_port(httpd)}/api/jobs/x/cancel",
            {"session_id": "nope"},
        )
        # cancel_session не нашёл активный turn → {"ok": False} → конфликт (409)
        assert status == 409, (status, body)
        assert body.get("ok") is False
    finally:
        httpd.shutdown()


# --- unit: мягкая отмена на границе retry через ConversationAgent.turn ---
def test_retry_boundary_cancel_via_cancel_check():
    """Retry-boundary отмена: semantic verification → retry → cancel_check → CANCELLED.

    Тестирует логику из conversation.py turn() (line ~461): decision.action=="retry"
    → cancel_check() → CANCELLED + ctx.messages append "cancelled".
    """
    store = AssetStore(root="__tmp_cancel_retrybnd__")
    # retry-политика допускает retry для 'verification'; 3 attempts
    policy = RetryPolicy(max_attempts=3, backoff_base=0.01, backoff_max=0.05)
    provider = FakeProvider()

    # --- без отмены: 3 попытки FAIL (verification) → FAILED ---
    agent = ConversationAgent(
        store,
        semantic_verifier=_FailingSemVerifier(),
        retry_policy=policy,
    )
    job = agent.turn(
        "sess-rb",
        capability="image.generate",
        request="сделай кота",
        max_attempts=3,
        provider=provider,
        ws_timeout=10,
    )
    assert job.state.value == "FAILED", f"ожидали FAILED, получили {job.state.value}"
    ctx = agent.session("sess-rb")
    assert any(m.get("type") == "decision_failed" for m in ctx.messages), ctx.messages

    # --- с отменой: флаг поставлен ДО turn → CANCELLED на границе первой попытки ---
    flag = threading.Event()
    flag.set()  # уже «отменено»
    agent2 = ConversationAgent(
        store,
        semantic_verifier=_FailingSemVerifier(),
        retry_policy=policy,
    )
    job2 = agent2.turn(
        "sess-rb2",
        capability="image.generate",
        request="другой кот",
        max_attempts=3,
        provider=provider,
        cancel_check=flag.is_set,
        ws_timeout=10,
    )
    assert job2.state.value == "CANCELLED", f"ожидали CANCELLED, получили {job2.state.value}"
    ctx2 = agent2.session("sess-rb2")
    assert any(m.get("type") == "cancelled" for m in ctx2.messages), ctx2.messages
    assert ctx2.dialog_state == "idle", ctx2.dialog_state


# --- sensor: verify that run_turn wires cancel_check from session flag ---
def test_soft_cancel_e2e_via_ui():
    """Мягкая отмена живого turn через HTTP (/api/jobs/.../cancel + session_id).

    Проверяет полный путь:
      /turn → run_turn (threading.Event flag set) → cancel_check видит флаг
      POST /api/jobs/x/cancel {"session_id": "soft-sid"} → flag.set()
      turn() → CANCELLED на границе retry (или до запуска graph)

    run_turn() не передаёт max_attempts>1, поэтому отмена срабатывает на
    top-of-loop check (line 309): до первого engine.execute, если флаг уже стоит.
    """
    store = AssetStore(root="__tmp_cancel_soft__")
    httpd, factory = _server(store)
    try:
        # запустить turn (он ставит flag в active_cancel_flags и стартует поток)
        factory.run_turn("soft-sid", capability="image.generate", request="кот")
        # дать потоку стартовать и установить active_cancel_flags
        for _ in range(50):
            if factory.active_cancel_flags.get("soft-sid"):
                break
            time.sleep(0.02)
        assert factory.active_cancel_flags.get("soft-sid"), "флаг активного turn не установлен"

        # мягкая отмена через HTTP
        st, body = _post_json(
            f"http://127.0.0.1:{_port(httpd)}/api/jobs/x/cancel",
            {"session_id": "soft-sid"},
        )
        assert body.get("ok") is True, body
        assert body.get("state") == "cancel requested"

        # флаг сброшен после завершения turn (finally block в run_turn).
        # run_turn использует ws_timeout=15s дефолт, поэтому turn может занять
        # >15s (WS-track timeout падает на FakeClient → /history fallback).
        for _ in range(2000):
            if "soft-sid" not in factory.active_cancel_flags:
                break
            time.sleep(0.02)
        assert "soft-sid" not in factory.active_cancel_flags, "флаг не сброшен"
    finally:
        httpd.shutdown()