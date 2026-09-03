"""M7 — Conversation Context (многоходовый контекст поверх Agent).

Доказывает offline (без LLM, без ComfyUI):
  - multi-turn chain: generate → Asset A → image.edit (active_asset) → Asset B, lineage(B)==[B,A];
  - session isolation (разные session не видят чужие active_asset/assets);
  - explicit asset override активного;
  - ошибка НЕ заменяет active_asset;
  - type-mismatch active_asset → unresolved (AD-23, без транскодинга);
  - media-agnostic invariant (ConversationContext хранит только id/строки).

Real-E2E chain (turn1 generate → turn2 image.edit на active_asset) — skip без COMFY_REMOTE_URL.
"""
from __future__ import annotations

import base64
import os

import pytest

from app.assets.store import AssetStore
from app.conversation import ConversationAgent, ConversationContext
from app.engine import JobState

_1PX_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)

COMFY_REMOTE_URL = os.environ.get("COMFY_REMOTE_URL")


class FakeClient:
    def __init__(self, base_url: str = "http://127.0.0.1:9999") -> None:
        self.base_url = base_url

    def get_system_stats(self):
        raise RuntimeError("offline fake client")

    def get_object_info(self) -> dict:
        return {}

    def view(self, filename: str, subfolder: str = "", type_: str = "output") -> bytes:
        if filename.endswith(".wav"):
            return b"RIFF\x00\x00\x00\x00WAVEfmt "
        if filename.endswith((".png", ".jpg")):
            return b"\x89PNG\r\n\x1a\n"
        if filename.endswith(".mp4"):
            return b"\x00\x00\x00\x18ftypmp42"
        return b"data"


class FakeProvider:
    _counter = 0

    def __init__(self, backend_id: str = "fake_comfyui") -> None:
        self.client = FakeClient()
        self.backend_id = backend_id

    def upload_asset(self, asset):
        from app.provider.backend_ref import BackendRef
        from pathlib import Path
        return BackendRef(
            provider="comfyui", backend=self.backend_id,
            reference={"filename": Path(asset.path).name, "subfolder": "", "type": "input"},
        )

    def execute(self, prompt: dict, client_id=None) -> str:
        FakeProvider._counter += 1
        return f"fake-prompt-id-{FakeProvider._counter}"

    def get_job(self, prompt_id: str) -> dict:
        return {
            prompt_id: {
                "status": {"status_str": "success"},
                "outputs": {
                    "9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]},
                    "8": {"gifs": [{"filename": "out.mp4", "subfolder": "", "type": "output"}]},
                    "2": {"audio": [{"filename": "out.wav", "subfolder": "multimodal", "type": "output"}]},
                },
            }
        }

    def view(self, ref):
        return self.client.view(ref.reference["filename"])

    def cancel(self, prompt_id: str) -> None:
        pass

    def discover_checkpoints(self) -> list:
        return []


class BrokenProvider(FakeProvider):
    """view возвращает битые данные → Verifier/validate_output_bytes падает (point 8)."""

    def view(self, ref):
        return b"corrupted-bytes"


def _gen_params():
    return {"prompt": "a cat", "negative_prompt": "", "width": 256, "height": 256, "seed": 0, "steps": 5}


def _edit_params():
    return {"prompt": "make it photorealistic", "negative_prompt": "", "seed": 0, "steps": 5, "denoise": 0.6}


# --------------------------------------------------------------------------- #

def test_conversation_context_fields():
    ctx = ConversationContext(session_id="s1")
    d = ctx.as_dict()
    for key in ("messages", "assets", "jobs", "workflows", "parameters",
                "active_task", "active_workflow", "active_job", "active_asset",
                "unresolved", "dialog_state"):
        assert key in d, f"ConversationContext не содержит {key}"
    assert d["session_id"] == "s1"
    assert d["dialog_state"] == "idle"


def test_multi_turn_chain_offline(tmp_path):
    store = AssetStore(root=tmp_path)
    agent = ConversationAgent(store)
    provider = FakeProvider()

    # turn 1: generate → Asset A
    j1 = agent.turn("s1", capability="image.generate", params=_gen_params(), provider=provider)
    assert j1.state == JobState.SUCCESS
    a_id = j1.output_assets[0]
    a = store.get(a_id)
    assert a.type == "image"
    assert agent.active_asset_id("s1") == a_id

    # turn 2: «сделай реалистичнее» → image.edit с active_asset=A → Asset B
    j2 = agent.turn("s1", capability="image.edit", params=_edit_params(), provider=provider)
    assert j2.state == JobState.SUCCESS
    b_id = j2.output_assets[0]
    b = store.get(b_id)
    assert b.type == "image"
    # lineage(B) == [B, A]
    assert b.source_asset == a_id
    assert store.lineage(b_id) == [b, a]
    # active_asset теперь B
    assert agent.active_asset_id("s1") == b_id

    # turn 3: active_asset == B
    ctx = agent.context("s1")
    assert ctx.active_asset == b_id
    assert ctx.active_workflow == "img2img@1.0.0"
    assert ctx.active_job == j2.prompt_id
    assert a_id in ctx.assets and b_id in ctx.assets
    assert len(ctx.jobs) == 2


def test_session_isolation(tmp_path):
    store = AssetStore(root=tmp_path)
    agent = ConversationAgent(store)
    provider = FakeProvider()

    ja = agent.turn("A", capability="image.generate", params=_gen_params(), provider=provider)
    jb = agent.turn("B", capability="image.generate", params=_gen_params(), provider=provider)
    a_id = ja.output_assets[0]
    b_id = jb.output_assets[0]
    assert a_id != b_id

    ctx_a = agent.context("A")
    ctx_b = agent.context("B")
    # разные активные ассеты
    assert ctx_a.active_asset == a_id
    assert ctx_b.active_asset == b_id
    # session A не видит Asset B, session B не видит Asset A
    assert b_id not in ctx_a.assets
    assert a_id not in ctx_b.assets
    assert ctx_a.active_job != ctx_b.active_job


def test_explicit_asset_overrides_active(tmp_path):
    store = AssetStore(root=tmp_path)
    agent = ConversationAgent(store)
    provider = FakeProvider()

    j1 = agent.turn("s1", capability="image.generate", params=_gen_params(), provider=provider)
    a_id = j1.output_assets[0]

    # явный входной файл C (image) — должен переопределить active_asset A
    c_path = tmp_path / "c.png"
    c_path.write_bytes(_1PX_PNG)
    j2 = agent.turn("s1", capability="image.edit", params=_edit_params(),
                    assets={"image": str(c_path)}, provider=provider)
    assert j2.state == JobState.SUCCESS
    b_id = j2.output_assets[0]
    b = store.get(b_id)
    # B порождён от явного C, а не от active A
    assert b.source_asset != a_id
    # явный asset инджестился как input-ассет (source_asset=None) → его id в качестве source
    c_asset = store.get(b.source_asset)
    assert c_asset is not None and c_asset.source_asset is None
    assert c_asset.id == b.source_asset


def test_error_does_not_replace_active_asset(tmp_path):
    store = AssetStore(root=tmp_path)
    agent = ConversationAgent(store)
    provider = FakeProvider()

    j1 = agent.turn("s1", capability="image.generate", params=_gen_params(), provider=provider)
    a_id = j1.output_assets[0]
    assert agent.active_asset_id("s1") == a_id

    # turn 2 падает (битый выхлоп) → active_asset НЕ заменяется
    with pytest.raises(Exception):
        agent.turn("s1", capability="image.edit", params=_edit_params(), provider=BrokenProvider())

    ctx = agent.context("s1")
    assert ctx.active_asset == a_id           # остался прежним
    assert ctx.dialog_state == "error"
    assert ctx.unresolved                       # зафиксировано нерешённое требование/ошибка
    assert store.get(a_id) is not None and store.get(a_id).type == "image"


def test_active_asset_type_mismatch_is_unresolved(tmp_path):
    store = AssetStore(root=tmp_path)
    agent = ConversationAgent(store)
    provider = FakeProvider()

    # active_asset — video (из video.generate)
    jv = agent.turn("s1", capability="video.generate",
                    params={"prompt": "a cat", "negative_prompt": "", "width": 512, "height": 512,
                            "frames": 4, "seed": 0, "steps": 20, "fps": 4},
                    provider=provider)
    assert jv.state == JobState.SUCCESS
    v_id = jv.output_assets[0]
    assert store.get(v_id).type == "video"
    assert agent.active_asset_id("s1") == v_id

    # image.edit требует image; active — video → тип не совпадает → unresolved (без транскодинга)
    with pytest.raises(Exception):
        agent.turn("s1", capability="image.edit", params=_edit_params(), provider=provider)

    ctx = agent.context("s1")
    # active_asset НЕ изменился на video→image автоматически; остался video
    assert ctx.active_asset == v_id
    assert ctx.unresolved


def test_resolve_asset_inputs_priority_and_active(tmp_path):
    store = AssetStore(root=tmp_path)
    agent = ConversationAgent(store)
    provider = FakeProvider()

    # создаём active image asset вручную (как если бы он появился на прошлом ходе)
    ap = tmp_path / "active.png"
    ap.write_bytes(_1PX_PNG)
    active = store.ingest(ap, type="image", role="output")

    class _Ctx:
        active_asset = active.id

    # 1) active fallback (без explicit) → возвращает id active
    out = agent.resolve_asset_inputs(context=_Ctx(), store=store, as_ids=True,
                                     required_roles={"image": "image"})
    assert out == {"image": active.id}

    # 2) explicit переопределяет active
    ep = tmp_path / "explicit.png"
    ep.write_bytes(_1PX_PNG)
    out2 = agent.resolve_asset_inputs({"image": str(ep)}, context=_Ctx(), store=store, as_ids=True,
                                      required_roles={"image": "image"})
    assert out2["image"] != active.id   # новый input-ассет из явного пути

    # 3) type mismatch active (video) для role image → не разрешается
    vp = tmp_path / "v.mp4"
    vp.write_bytes(b"ftypmp4")
    vid = store.ingest(vp, type="video", role="output")

    class _CtxV:
        active_asset = vid.id

    out3 = agent.resolve_asset_inputs(context=_CtxV(), store=store, as_ids=True,
                                     required_roles={"image": "image"})
    assert "image" not in out3


@pytest.mark.skipif(
    not COMFY_REMOTE_URL,
    reason="COMFY_REMOTE_URL не задан — нет remote ComfyUI для real M7 chain (без mock не проверяем).",
)
def test_real_conversation_chain_remote(tmp_path):
    from app.comfy.client import ComfyClient
    from app.provider.comfyui import ComfyUIProvider

    client = ComfyClient(base_url=COMFY_REMOTE_URL, timeout=120)
    try:
        client.get_system_stats()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"remote ComfyUI недоступен: {e}")

    store = AssetStore(root=tmp_path)
    agent = ConversationAgent(store)
    provider = ComfyUIProvider(client, backend_id="remote_comfyui")

    # turn 1: реальная генерация → Asset A
    j1 = agent.turn("s1", capability="image.generate", params=_gen_params(), provider=provider, ws_timeout=360)
    assert j1.state == JobState.SUCCESS
    a_id = j1.output_assets[0]
    assert store.get(a_id).type == "image"

    # turn 2: «сделай реалистичнее» → image.edit на active_asset A → реальный img2img → Asset B
    j2 = agent.turn("s1", capability="image.edit", params=_edit_params(), provider=provider, ws_timeout=360)
    assert j2.state == JobState.SUCCESS
    b_id = j2.output_assets[0]
    b = store.get(b_id)
    assert b.type == "image"
    assert b.source_asset == a_id
    assert store.lineage(b_id) == [b, store.get(a_id)]
    assert agent.active_asset_id("s1") == b_id
