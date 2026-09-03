"""Agent (главная задача) — media-agnostic оркестрация без реального ComfyUI.

Проверяет, что Agent связывает Registry + Engine и исполняет capability
image.generate / video.generate / audio.generate единым путём (без ветвления
по media), используя FakeProvider/FakeClient вместо сети.
"""
from __future__ import annotations

import os
from pathlib import Path

from app.assets.store import AssetStore
from app.agent import Agent, AgentError
from app.engine import JobState
from app.provider.backend_ref import BackendRef
from app.registry.backends import BackendCatalog, BackendSpec


class FakeClient:
    """Заглушка ComfyClient: сеть не нужна, engine ходит в get_job/view."""

    def __init__(self, base_url: str = "http://127.0.0.1:9999") -> None:
        self.base_url = base_url

    def get_system_stats(self):
        raise RuntimeError("offline fake client")

    def get_object_info(self) -> dict:
        return {}  # без чекпоинтов → _bind_models не биндит

    def view(self, filename: str, subfolder: str = "", type_: str = "output") -> bytes:
        if filename.endswith(".wav"):
            return b"RIFF\x00\x00\x00\x00WAVEfmt "  # валидный WAV-заголовок
        if filename.endswith((".png", ".jpg")):
            return b"\x89PNG\r\n\x1a\n"
        if filename.endswith(".mp4"):
            return b"\x00\x00\x00\x18ftypmp42"
        return b"data"


class FakeProvider:
    """Заглушка ComfyUIProvider: execute возвращает pid, get_job — готовые выходы."""

    def __init__(self, backend_id: str = "fake_comfyui") -> None:
        self.client = FakeClient()
        self.backend_id = backend_id

    def upload_asset(self, asset) -> BackendRef:
        return BackendRef(
            provider="comfyui", backend=self.backend_id,
            reference={"filename": Path(asset.path).name, "subfolder": "", "type": "input"},
        )

    def execute(self, prompt: dict, client_id=None) -> str:
        return "fake-prompt-id"

    def get_job(self, prompt_id: str) -> dict:
        # Все возможные save-ноды сразу — engine возьмёт нужную по manifest.outputs.
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

    def view(self, ref: BackendRef) -> bytes:
        return self.client.view(ref.reference["filename"])

    def cancel(self, prompt_id: str) -> None:
        pass

    def discover_checkpoints(self) -> list:
        return []


def _params(capability: str) -> dict:
    if capability == "image.generate":
        return {"prompt": "a cat", "negative_prompt": "", "width": 512, "height": 512, "seed": 0, "steps": 20}
    if capability == "video.generate":
        return {"prompt": "a cat", "negative_prompt": "", "width": 512, "height": 512,
                "frames": 4, "seed": 0, "steps": 20, "fps": 4}
    if capability == "audio.generate":
        return {"prompt": "a calm beat", "duration": 8.0, "seed": 0}
    raise AssertionError(capability)


_EXPECT_KIND = {
    "image.generate": "image",
    "video.generate": "video",
    "audio.generate": "audio",
}


def test_agent_discovers_capabilities():
    store = AssetStore(root="__tmptest_agent__")
    agent = Agent(store)
    caps = agent.capabilities()
    for c in ("image.generate", "video.generate", "audio.generate"):
        assert c in caps, f"capability {c} не обнаружен"


def test_agent_media_agnostic_run(tmp_path):
    store = AssetStore(root=tmp_path)
    agent = Agent(store)
    provider = FakeProvider()
    for capability in ("image.generate", "video.generate", "audio.generate"):
        job = agent.run(capability, params=_params(capability), provider=provider)
        assert job.state == JobState.SUCCESS, f"{capability}: {job.state}"
        assert len(job.output_assets) == 1
        out = store.get(job.output_assets[0])
        assert out is not None
        assert out.type == _EXPECT_KIND[capability], f"{capability}: тип {out.type}"
        assert out.created_from == job.prompt_id


def test_agent_unknown_capability_raises():
    store = AssetStore(root="__tmptest_agent_x__")
    agent = Agent(store)
    try:
        agent.run("nonexistent.generate")
        assert False, "ожидалась AgentError"
    except AgentError:
        pass


def test_agent_multi_backend_selects_highest_priority(monkeypatch, tmp_path):
    captured: dict = {}

    def fake_build(backend_id, base_url=None):
        captured["backend_id"] = backend_id
        return FakeProvider(backend_id=backend_id)

    monkeypatch.setattr("app.agent._build_provider", fake_build)
    store = AssetStore(root=tmp_path)
    cat = BackendCatalog([
        BackendSpec("local_comfyui", "http://127.0.0.1:8188", priority=0),
        BackendSpec("remote_comfyui", "http://gpu:8188", priority=10),
    ])
    agent = Agent(store, backends=cat)
    job = agent.run("image.generate", params=_params("image.generate"))
    assert captured["backend_id"] == "remote_comfyui"
    assert job.state == JobState.SUCCESS


def test_agent_multi_backend_capability_filter(monkeypatch, tmp_path):
    captured: dict = {}

    def fake_build(backend_id, base_url=None):
        captured["backend_id"] = backend_id
        return FakeProvider(backend_id=backend_id)

    monkeypatch.setattr("app.agent._build_provider", fake_build)
    store = AssetStore(root=tmp_path)
    cat = BackendCatalog([
        BackendSpec("local_comfyui", "http://a", priority=10, capabilities={"image.generate"}),
        BackendSpec("remote_comfyui", "http://b", priority=100, capabilities={"video.generate"}),
    ])
    agent = Agent(store, backends=cat)

    agent.run("video.generate", params=_params("video.generate"))
    assert captured["backend_id"] == "remote_comfyui"

    captured.clear()
    agent.run("audio.generate", params=_params("audio.generate"))
    assert captured["backend_id"] == "local_comfyui"  # capability ни у кого нет → fallback backend_id


def test_agent_generate_with_heuristic_planner(monkeypatch, tmp_path):
    monkeypatch.setattr("app.agent._build_provider", lambda bid, base_url=None: FakeProvider(bid))
    store = AssetStore(root=tmp_path)
    agent = Agent(store)  # planner=None → HeuristicPlanner
    job = agent.generate("сделай lo-fi трек про океан")
    assert job.state == JobState.SUCCESS
    out = store.get(job.output_assets[0])
    assert out.type == "audio"


def test_agent_generate_uses_llm_planner(monkeypatch, tmp_path):
    captured: dict = {}

    class _StubPlan:
        capability = "video.generate"
        params = {"prompt": "x"}
        rationale = "llm"

    class _StubLLM:
        def plan(self, request):
            captured["request"] = request
            return _StubPlan()

    monkeypatch.setattr("app.agent._build_provider", lambda bid, base_url=None: FakeProvider(bid))
    store = AssetStore(root=tmp_path)
    agent = Agent(store, planner=_StubLLM())
    job = agent.generate("animate a cat")
    assert captured["request"] == "animate a cat"
    assert job.state == JobState.SUCCESS


def test_resolve_asset_inputs_path_and_base64():
    import base64

    assert Agent.resolve_asset_inputs({"img": "/tmp/x.png"}) == {"img": "/tmp/x.png"}
    data = base64.b64encode(b"hello").decode("ascii")
    out = Agent.resolve_asset_inputs({"img": {"data": data, "name": "x.png"}})
    p = out["img"]
    assert p.endswith(".png")
    try:
        with open(p, "rb") as f:
            assert f.read() == b"hello"
    finally:
        os.remove(p)
