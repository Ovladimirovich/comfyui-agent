"""S7 — «Композитор»: условно-событийная композиция запросов.

Ключевые маркеры: «когда» (вкл. «когда захочешь», «когда будет готово»),
«затем» (M18), «как только». Проверяет:
  1) TaskDecomposer: «когда будет готово» / «когда захочешь» → [start, next];
  2) «затем»/«потом» и «и» (регрессия M18) продолжают работать;
  3) «когда-нибудь»/«когда-то» НЕ являются маркером (не разбивают);
  4) ConversationAgent: turn «нарисуй кота, когда будет готово увеличь разрешение»
     → ExecutionChain 2 шага (generate → upscale), активный workflow последнего
     шага, upstream output попадает в следующий шаг (source_asset);
  5) UI/API: POST /api/chat с запросом «когда» → активный workflow
     последнего шага.

Offline: FakeProvider (как test_s9_planner_routing.py), патч discover_runtime.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from app.assets.store import AssetStore
from app.conversation import ConversationAgent
from app.engine import JobState
from app.planner.decomposer import TaskDecomposer
from app.registry.runtime import RuntimeInfo
from app.ui import ComfyUIServer, _make_handler


# AD-18 strict: runtime с fp16=True + checkpoint нужны для generate/upscale.
_FAKE_RUNTIME = RuntimeInfo(
    accelerator="directml", vram_gb=12.0, fp16=True, xformers=False,
    lowvram=True, comfyui_version="0.34.5",
)


class FakeClient:
    def __init__(self, base_url="http://127.0.0.1:9999"):
        self.base_url = base_url

    def get_system_stats(self):
        raise RuntimeError("offline")

    def get_object_info(self):
        return {}

    def discover_checkpoints(self) -> list[str]:
        return ["checkpoint"]

    def view(self, filename, subfolder="", type_="output"):
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
            "30": {"images": [{"filename": "upscaled.png", "subfolder": "", "type": "output"}]},
        }}}

    def view(self, ref):
        return self.client.view(ref.reference["filename"])

    def cancel(self, prompt_id):
        pass

    def discover_checkpoints(self):
        return []


def _post_json(url, obj):
    data = json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


# --- 1. TaskDecomposer: «когда»-маркеры ---

def test_decompose_when_ready():
    """Разделение по «когда будет готово» через конъюнкцию " когда ".
    Вторая часть содержит "увеличь" → upscale."""
    d = TaskDecomposer()
    parts = d.decompose("нарисуй кота, когда будет готово увеличь разрешение")
    caps = [p.capability for p in parts]
    assert caps == ["image.generate", "image.upscale"], f"caps={caps}"
    assert "нарисуй кота" in parts[0].description
    assert "увеличь" in parts[1].description


def test_decompose_when_want_no_comma():
    """Без запятой: " когда " — единственный разделитель."""
    d = TaskDecomposer()
    parts = d.decompose("нарисуй кота когда захочешь увеличь")
    caps = [p.capability for p in parts]
    assert caps == ["image.generate", "image.upscale"], f"caps={caps}"
    assert "нарисуй кота" in parts[0].description
    assert "увеличь" in parts[1].description


def test_decompose_zatem_regression():
    d = TaskDecomposer()
    parts = d.decompose("нарисуй кота, затем увеличь")
    caps = [p.capability for p in parts]
    assert caps == ["image.generate", "image.upscale"], f"caps={caps}"


def test_decompose_and_regression():
    d = TaskDecomposer()
    parts = d.decompose("нарисуй кота и увеличь разрешение")
    caps = [p.capability for p in parts]
    assert caps == ["image.generate", "image.upscale"], f"caps={caps}"


def test_decompose_when_not_marker():
    d = TaskDecomposer()
    # «когда-нибудь»/«когда-то» не содержат " когда " (пробелы по краям)
    for t in ("нарисуй кота когда-нибудь", "сделай логотип когда-то"):
        parts = d.decompose(t)
        assert len(parts) == 1, f"{t!r} -> {parts}"


def test_decompose_single_still_single():
    d = TaskDecomposer()
    assert len(d.decompose("просто нарисуй кота")) == 1


# --- 2. ConversationAgent: «когда»-цепочка (generate → upscale) ---

def test_conversation_when_chain():
    store = AssetStore(root="__tmptest_s7_chain__")
    agent = ConversationAgent(store)
    provider = FakeProvider()
    with patch("app.agent.discover_runtime", return_value=_FAKE_RUNTIME):
        j = agent.turn("s7", request="нарисуй кота, когда будет готово увеличь разрешение",
                       provider=provider)
    assert j.state == JobState.SUCCESS, j.error
    ctx = agent.session("s7")
    assert ctx.active_workflow.startswith("upscale@"), f"workflow={ctx.active_workflow}"
    assert j.output_assets, "upscale должен создать output"
    out = store.get(j.output_assets[-1])
    assert out is not None and out.source_asset is not None, "upstream output должен быть связан"


# --- 3. UI/API: /api/chat с «когда»-запросом → цепочка, последний шаг ---

def test_ui_chat_when_chain():
    store = AssetStore(root="__tmptest_s7_ui__")
    agent = ConversationAgent(store)
    factory = ComfyUIServer(store, agent=agent, provider=FakeProvider())
    handler = _make_handler(factory)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        sid = "s7-ui"
        workflow = None
        ctx = None
        with patch("app.agent.discover_runtime", return_value=_FAKE_RUNTIME):
            status, res = _post_json(f"{base}/api/chat", {
                "session_id": sid,
                "request": "нарисуй кота, когда будет готово увеличь разрешение",
            })
            assert status == 200, res
            for _ in range(200):
                with urllib.request.urlopen(f"{base}/api/session?session_id={sid}", timeout=5) as r:
                    ctx = json.loads(r.read())
                if ctx.get("active_workflow"):
                    workflow = ctx["active_workflow"]
                    break
                time.sleep(0.05)
        assert workflow and workflow.startswith("upscale@"), f"workflow={workflow}"
        assert ctx.get("active_asset"), "должен быть активный ассет последнего шага"
    finally:
        httpd.shutdown()
