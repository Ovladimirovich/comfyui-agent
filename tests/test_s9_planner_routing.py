"""S9 — маршрутизация вложенного изображения (multimodal input) в image.edit.

Проверяет (см. docs/AGENT_UI_UI3_DESIGN.md S9, PROJECT_SPEC §21 POST /api/assets):
  1) HeuristicPlanner: explicit image attach текущего turn → image.edit
     (даже без edit-ключевых слов, напр. «сделай это изображение в стиле акварели»);
  2) explicit image + НЕТ image.edit в capabilities → fallback image.generate;
  3) media/text-ключевые слова имеют приоритет над вложением;
  4) upscale-хинт побеждает explicit attach;
  5) session.active только (без explicit) + generate-запрос → image.generate (регрессия);
  6) без контекста → image.generate;
  7) ConversationAgent: turn с explicit asset + стилевой запрос → img2img@ + lineage;
  8) UI: POST /api/assets (multipart) → /api/chat с assets → img2img@ workflow.

Offline: FakeProvider (как test_planner_context.py). Без реального ComfyUI.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import urllib.request  # noqa: F401 (см. _post_json)
import urllib.error
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from app.assets.store import AssetStore
from app.agent import Agent
from app.conversation import ConversationAgent
from app.engine import JobState
from app.planner import HeuristicPlanner, PlanContext
from app.registry.runtime import RuntimeInfo
from app.ui import ComfyUIServer, _make_handler


# --- FakeProvider (как test_planner_context.py / test_ui_cancel_assets_m9b.py) ---

# AD-18 strict: runtime с fp16=True нужен для img2img/video_generate,
# иначе _select_manifest выбрасывает AgentError (нет подтверждённой совместимости).
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
        # AD-18 strict: required_models=["checkpoint"] требует наличие модели.
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


def _make_image_asset(store):
    """Создать image-ассет для тестов (валидный PNG-заголовок)."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png", prefix="test_s9_img_")
    tmp.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    tmp.close()
    try:
        return store.ingest(tmp.name, type="image", role="input")
    finally:
        os.unlink(tmp.name)


def _post_json(url, obj):
    data = json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


# --- 1. explicit image attach → image.edit (даже без edit-ключевых слов) ---

def test_explicit_image_attach_routes_to_edit():
    planner = HeuristicPlanner()
    caps = ("image.generate", "image.edit", "image.upscale", "video.generate",
            "audio.generate", "text.generate")
    ctx = PlanContext(active_asset_type="image", explicit_asset_type="image", capabilities=caps)
    for req in (
        "сделай это изображение в стиле акварели",
        "преврати картинку в мультяшку",
        "сделай это изображение ночью",
        "этот снимок в стиле киберпанк",
    ):
        r = planner.plan(req, context=ctx)
        assert r.capability == "image.edit", f"'{req}' → {r.capability}"
        assert r.rationale == "explicit_image_attach"


# --- 2. explicit image + НЕТ image.edit → fallback image.generate ---

def test_explicit_image_edit_unavailable_falls_back():
    planner = HeuristicPlanner()
    ctx = PlanContext(active_asset_type="image", explicit_asset_type="image",
                      capabilities=("image.generate",))
    r = planner.plan("сделай это изображение в стиле акварели", context=ctx)
    assert r.capability == "image.generate"


# --- 3. media/text-ключевые слова имеют приоритет над вложением ---

def test_explicit_image_does_not_shadow_media_or_text():
    planner = HeuristicPlanner()
    caps = ("image.generate", "image.edit", "audio.generate", "video.generate", "text.generate")
    ctx = PlanContext(active_asset_type="image", explicit_asset_type="image", capabilities=caps)
    assert planner.plan("сделай lo-fi трек про дождь", context=ctx).capability == "audio.generate"
    assert planner.plan("сгенерируй видео с котом", context=ctx).capability == "video.generate"
    assert planner.plan("напиши эссе про зиму", context=ctx).capability == "text.generate"


# --- 4. upscale-хинт побеждает explicit attach (тоже input-трансформация) ---

def test_explicit_image_upscale_hint_wins():
    planner = HeuristicPlanner()
    caps = ("image.generate", "image.edit", "image.upscale")
    ctx = PlanContext(active_asset_type="image", explicit_asset_type="image", capabilities=caps)
    r = planner.plan("увеличь разрешение", context=ctx)
    assert r.capability == "image.upscale"


# --- 5. session.active только (без explicit) + generate-запрос → image.generate ---

def test_session_active_image_without_explicit_stays_generate():
    """«сгенерируй собаку» после сгенерированной картинки НЕ должен стать image.edit."""
    planner = HeuristicPlanner()
    ctx = PlanContext(active_asset_type="image", capabilities=("image.generate", "image.edit"))
    r = planner.plan("сгенерируй собаку", context=ctx)
    assert r.capability == "image.generate"
    r2 = planner.plan("нарисуй замок на скале", context=ctx)
    assert r2.capability == "image.generate"


# --- 6. без контекста → image.generate (fallback сохранён) ---

def test_no_context_default():
    planner = HeuristicPlanner()
    r = planner.plan("сделай это изображение в стиле акварели")
    assert r.capability == "image.generate"


# --- Agent.explicit_asset_type: резолюция типа без изменения active_asset ---

def test_explicit_asset_type_resolution():
    store = AssetStore(root="__tmptest_s9_type__")
    img = _make_image_asset(store)
    assert Agent.explicit_asset_type({"image": {"asset_id": img.id}}, store=store) == "image"
    assert Agent.explicit_asset_type({"image": "photo.png"}, store=None) == "image"
    assert Agent.explicit_asset_type({}, store=store) is None
    assert Agent.explicit_asset_type(None, store=store) is None


# --- 7. ConversationAgent: explicit asset + стилевой запрос → img2img@ + lineage ---

def test_conversation_explicit_image_style_request_img2img():
    store = AssetStore(root="__tmptest_s9_conv__")
    agent = ConversationAgent(store)
    provider = FakeProvider()
    attached = _make_image_asset(store)
    with patch("app.agent.discover_runtime", return_value=_FAKE_RUNTIME):
        j = agent.turn("s9", request="сделай это изображение в стиле акварели",
                       assets={"image": {"asset_id": attached.id}}, provider=provider)
    assert j.state == JobState.SUCCESS
    ctx = agent.session("s9")
    assert ctx.active_workflow.startswith("img2img@"), ctx.active_workflow
    assert j.output_assets, "image.edit должен создать output"
    out = store.get(j.output_assets[0])
    assert out.source_asset == attached.id, "output должен быть порождён от явного вложения"


# --- 8. UI: POST /api/assets (multipart) → /api/chat с assets → img2img@ ---

def test_ui_upload_then_chat_with_assets_image_edit():
    store = AssetStore(root="__tmptest_s9_ui__")
    factory = ComfyUIServer(store, agent=ConversationAgent(store), provider=FakeProvider())
    handler = _make_handler(factory)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        port = httpd.server_address[1]
        base = f"http://127.0.0.1:{port}"
        sid = "s9-ui"

        # 1) загрузка вложения
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        boundary = "S9-BOUNDARY"
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
            f"{base}/api/assets", data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            uploaded = json.loads(r.read())
        assert uploaded.get("asset_id")
        assert uploaded.get("type") == "image"
        aid = uploaded["asset_id"]

        # 2) чат с вложением (run_turn в фоновом потоке; discover_runtime — мок для offline,
        #    должен покрывать момент реального исполнения turn в фоне)
        workflow = None
        ctx = None
        with patch("app.agent.discover_runtime", return_value=_FAKE_RUNTIME):
            status, res = _post_json(f"{base}/api/chat", {
                "session_id": sid,
                "request": "сделай это изображение в стиле акварели",
                "assets": {"image": {"asset_id": aid}},
            })
            assert status == 200, res

            # 3) poll session → img2img@
            for _ in range(200):
                with urllib.request.urlopen(f"{base}/api/session?session_id={sid}", timeout=5) as r:
                    ctx = json.loads(r.read())
                if ctx.get("active_workflow"):
                    workflow = ctx["active_workflow"]
                    break
                time.sleep(0.05)
        assert workflow and workflow.startswith("img2img@"), f"workflow={workflow}"
        active = store.get(ctx["active_asset"])
        assert active is not None and active.source_asset == aid
    finally:
        httpd.shutdown()