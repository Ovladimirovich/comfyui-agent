"""Context-aware Planner (M9.1) — regression + интеграция с ConversationAgent/UI.

Проверяет:
  1) active image + edit-хинт → image.edit
  2) no active asset + edit-хинт → fallback (image.generate)
  3) active video + edit-хинт → НЕ image.edit (нет video.edit)
  4) explicit capability не переопределяется planner
  5) ConversationAgent: turn 1 generate → turn 2 «сделай реалистивнее» → image.edit → lineage(B)==[B,A]
  6) session isolation сохраняется
  7) старый вызов planner без context продолжает работать
  8) UI /turn: «сделай реалистивнее» → image.edit через HeuristicPlanner + ConversationAgent
  9) HeuristicPlanner: active image + upscale-хинт → image.upscale
  10) ConversationAgent: 3-turn chain generate → edit → upscale
  11) HeuristicPlanner: upscale-хинт без active_asset → fallback (image.generate)
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

from app.assets.store import AssetStore
from app.agent import Agent, AgentError
from app.conversation import ConversationAgent
from app.engine import JobState
from app.planner import HeuristicPlanner, PlanContext, PlanResult
from app.ui import ComfyUIServer, _make_handler


# --- FakeProvider (как test_agent.py) ---

class FakeClient:
    def __init__(self, base_url="http://127.0.0.1:9999"):
        self.base_url = base_url
    def get_system_stats(self):
        raise RuntimeError("offline")
    def get_object_info(self):
        return {}
    def view(self, filename, subfolder="", type_="output"):
        return b"\x89PNG\r\n\x1a\n"


class FakeProvider:
    def __init__(self, backend_id="fake_comfyui"):
        self.client = FakeClient()
        self.backend_id = backend_id
    def upload_asset(self, asset):
        from app.provider.backend_ref import BackendRef
        return BackendRef(provider="comfyui", backend=self.backend_id,
                          reference={"filename": asset.path.split("/")[-1], "subfolder": "", "type": "input"})
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
    import tempfile, os
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png", prefix="test_img_")
    tmp.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    tmp.close()
    try:
        return store.ingest(tmp.name, type="image")
    finally:
        os.unlink(tmp.name)


def _make_video_asset(store):
    tmp = __import__("tempfile").NamedTemporaryFile(delete=False, suffix=".mp4", prefix="test_vid_")
    tmp.write(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100)
    tmp.close()
    try:
        return store.ingest(tmp.name, type="video")
    finally:
        os.unlink(tmp.name)


# --- 1. HeuristicPlanner: active image + edit-hint → image.edit ---

def test_heuristic_edit_with_active_image():
    planner = HeuristicPlanner()
    ctx = PlanContext(active_asset_type="image", capabilities=["image.generate", "image.edit"])
    for hint in ("сделай реалистивнее", "улучши изображение", "улучши", "enhance", "improve",
                 "отредактируй", "make realistic", "better quality"):
        result = planner.plan(hint, context=ctx)
        assert result.capability == "image.edit", f"'{hint}' → {result.capability}, ожидалось image.edit"


# --- 2. HeuristicPlanner: no active asset + edit-hint → fallback ---

def test_heuristic_edit_without_active_fallback():
    planner = HeuristicPlanner()
    result = planner.plan("сделай реалистивнее")
    assert result.capability == "image.generate"
    ctx_no_active = PlanContext(active_asset_type=None, capabilities=["image.generate", "image.edit"])
    result2 = planner.plan("сделай реалистивнее", context=ctx_no_active)
    assert result2.capability == "image.generate"


# --- 3. HeuristicPlanner: active video + edit-hint → NOT image.edit ---

def test_heuristic_edit_with_active_video_no_image_edit():
    """active video + edit-hint → fallback на base mapping (video.generate не находит edit-хинты)."""
    planner = HeuristicPlanner()
    ctx = PlanContext(active_asset_type="video", capabilities=["video.generate"])
    result = planner.plan("сделай реалистивнее", context=ctx)
    # edit_cap = "video.edit" не в capabilities → fallback → base mapping
    # base: "видео" не найден в "сделай реалистивнее" → image.generate
    assert result.capability == "image.generate"


# --- 4. Explicit capability не переопределяется planner ---

def test_explicit_capability_not_overridden():
    """Если caller явно указал capability, planner не вызывается."""
    store = AssetStore(root="__tmptest_ctx_explicit__")
    agent = ConversationAgent(store)
    provider = FakeProvider()
    # turn 1: generate → Asset A
    j1 = agent.turn("s1", capability="image.generate",
                     params={"prompt": "кот", "width": 64, "height": 64, "seed": 0, "steps": 5},
                     provider=provider)
    assert j1.state == JobState.SUCCESS
    ctx = agent.session("s1")
    assert ctx.active_asset is not None
    # turn 2: explicit capability="image.generate" — planner НЕ должен менять на image.edit
    j2 = agent.turn("s2", capability="image.generate",
                     params={"prompt": "ещё кот", "width": 64, "height": 64, "seed": 1, "steps": 5},
                     provider=provider)
    assert j2.state == JobState.SUCCESS
    assert ctx.active_workflow.startswith("txt2img@")


# --- 5. ConversationAgent: turn 1 generate → turn 2 «сделай реалистивнее» → image.edit → lineage ---

def test_conversation_agent_edit_chain():
    store = AssetStore(root="__tmptest_ctx_chain__")
    agent = ConversationAgent(store)
    provider = FakeProvider()
    # turn 1: generate → Asset A
    j1 = agent.turn("s1", capability="image.generate",
                     params={"prompt": "кот", "width": 64, "height": 64, "seed": 0, "steps": 5},
                     provider=provider)
    assert j1.state == JobState.SUCCESS
    a_id = j1.output_assets[0]
    ctx = agent.session("s1")
    assert ctx.active_asset == a_id
    # turn 2: «сделай реалистивнее» → HeuristicPlanner + context → image.edit → Asset B
    j2 = agent.turn("s1", request="сделай реалистивнее", provider=provider)
    assert j2.state == JobState.SUCCESS
    assert j2.output_assets, "image.edit должен создать output"
    b_id = j2.output_assets[0]
    assert ctx.active_asset == b_id
    b = store.get(b_id)
    assert b.source_asset == a_id
    lineage = store.lineage(b_id)
    ids = [a.id for a in lineage]
    assert ids == [b_id, a_id]


# --- 6. Session isolation ---

def test_session_isolation_with_context_planner():
    store = AssetStore(root="__tmptest_ctx_iso__")
    agent = ConversationAgent(store)
    provider = FakeProvider()
    agent.turn("A", capability="image.generate",
               params={"prompt": "кот", "width": 64, "height": 64, "seed": 0, "steps": 5},
               provider=provider)
    agent.turn("B", capability="image.generate",
               params={"prompt": "пёс", "width": 64, "height": 64, "seed": 1, "steps": 5},
               provider=provider)
    ctx_a = agent.session("A")
    ctx_b = agent.session("B")
    assert ctx_a.active_asset != ctx_b.active_asset
    assert ctx_a.active_asset not in ctx_b.assets
    assert ctx_b.active_asset not in ctx_a.assets


# --- 7. Старый вызов planner без context ---

def test_heuristic_without_context():
    planner = HeuristicPlanner()
    for req, expected in [("сгенерируй кота", "image.generate"),
                          ("сделай видео клип", "video.generate"),
                          ("музыкальный трек", "audio.generate")]:
        result = planner.plan(req)
        assert result.capability == expected


# --- 8. UI /turn: «сделай реалистивнее» через ConversationAgent ---

def test_ui_turn_edit_via_heuristic():
    store = AssetStore(root="__tmptest_ctx_ui__")
    factory = ComfyUIServer(store, agent=ConversationAgent(store), provider=FakeProvider())
    handler = _make_handler(factory)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        port = httpd.server_address[1]
        base = f"http://127.0.0.1:{port}"
        sid = "ui-edit"
        # turn 1: generate
        data = json.dumps({"session_id": sid, "request": "сгенерируй кота"}).encode()
        req = urllib.request.Request(f"{base}/turn", data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        # дождаться active_asset
        for _ in range(50):
            resp = urllib.request.urlopen(f"{base}/api/session?session_id={sid}", timeout=5)
            if json.loads(resp.read()).get("active_asset"):
                break
            time.sleep(0.05)
        resp = urllib.request.urlopen(f"{base}/api/session?session_id={sid}", timeout=5)
        ctx1 = json.loads(resp.read())
        assert ctx1["active_asset"]
        a_id = ctx1["active_asset"]
        # turn 2: «сделай реалистивнее» → image.edit через HeuristicPlanner + context
        data2 = json.dumps({"session_id": sid, "request": "сделай реалистивнее"}).encode()
        req2 = urllib.request.Request(f"{base}/turn", data=data2, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req2, timeout=10)
        for _ in range(50):
            resp2 = urllib.request.urlopen(f"{base}/api/session?session_id={sid}", timeout=5)
            ctx2 = json.loads(resp2.read())
            if ctx2.get("active_asset") != a_id:
                break
            time.sleep(0.05)
        resp2 = urllib.request.urlopen(f"{base}/api/session?session_id={sid}", timeout=5)
        ctx2 = json.loads(resp2.read())
        assert ctx2["active_asset"] != a_id
        assert ctx2["active_workflow"].startswith("img2img@")
        b_id = ctx2["active_asset"]
        b = store.get(b_id)
        assert b.source_asset == a_id
    finally:
        httpd.shutdown()


# --- 9. HeuristicPlanner: active image + upscale-хинт → image.upscale ---

def test_heuristic_upscale_with_active_image():
    planner = HeuristicPlanner()
    caps = ["image.generate", "image.edit", "image.upscale"]
    ctx = PlanContext(active_asset_type="image", capabilities=caps)
    for hint in ("увеличь разрешение", "сделай крупнее", "upscale",
                 "масштабируй", "увеличь", "сделай в высоком разрешении"):
        result = planner.plan(hint, context=ctx)
        assert result.capability == "image.upscale", f"'{hint}' → {result.capability}, ожидалось image.upscale"


# --- 10. ConversationAgent: 3-turn chain generate → edit → upscale ---

def test_conversation_agent_three_turn_chain():
    """Полный 3-ходовый сценарий: generate → edit → upscale."""
    store = AssetStore(root="__tmptest_3turn__")
    agent = ConversationAgent(store)
    provider = FakeProvider()
    # turn 1: generate → Asset A
    j1 = agent.turn("s1", capability="image.generate",
                     params={"prompt": "кот", "width": 64, "height": 64, "seed": 0, "steps": 5},
                     provider=provider)
    assert j1.state == JobState.SUCCESS
    a_id = j1.output_assets[0]
    ctx = agent.session("s1")
    assert ctx.active_asset == a_id
    # turn 2: «сделай реалистивнее» → image.edit → Asset B
    j2 = agent.turn("s1", request="сделай реалистивнее", provider=provider)
    assert j2.state == JobState.SUCCESS
    b_id = j2.output_assets[0]
    assert ctx.active_asset == b_id
    assert ctx.active_workflow.startswith("img2img@")
    # turn 3: «увеличь разрешение» → image.upscale → Asset C
    j3 = agent.turn("s1", request="увеличь разрешение", provider=provider)
    assert j3.state == JobState.SUCCESS
    c_id = j3.output_assets[0]
    assert ctx.active_asset == c_id
    assert ctx.active_workflow.startswith("upscale@")
    # lineage: C → B → A
    c = store.get(c_id)
    assert c.source_asset == b_id
    lineage = store.lineage(c_id)
    ids = [a.id for a in lineage]
    assert ids == [c_id, b_id, a_id], f"lineage: {ids}"


# --- 11. HeuristicPlanner: upscale-хинт без active_asset → fallback ---

def test_heuristic_upscale_without_active_fallback():
    planner = HeuristicPlanner()
    result = planner.plan("увеличь разрешение")
    assert result.capability == "image.generate"
    ctx_no_active = PlanContext(active_asset_type=None,
                                capabilities=["image.generate", "image.edit", "image.upscale"])
    result2 = planner.plan("увеличь разрешение", context=ctx_no_active)
    assert result2.capability == "image.generate"
