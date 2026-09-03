"""M18 Real E2E — generate → upscale через реальный ComfyUI.

Запуск:
    cd C:\\cd\\ComfyUI_AMD\\agent
    python -m pytest tests/test_m18_e2e_real.py -v -s

Требования:
    - ComfyUI запущен на 127.0.0.1:8188
    - Workflow txt2img@1.0.0 и upscale@1.0.0 в workflows/
    - Модели загружены в ComfyUI
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.agent import Agent
from app.assets.store import AssetStore
from app.conversation import ConversationAgent
from app.engine import JobState
from app.engine.history import ExecutionHistory

COMFY_URL = "http://127.0.0.1:8188"
E2E_PARAMS = {"width": 128, "height": 128, "steps": 3, "seed": 42}
WS_TIMEOUT = 120


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    root = tmp_path_factory.mktemp("assets_e2e")
    return AssetStore(root=root)


@pytest.fixture(scope="module")
def history():
    return ExecutionHistory()


@pytest.fixture(scope="module")
def agent(store, history):
    a = Agent(asset_store=store, execution_history=history)
    assert len(a.registry.workflows) >= 2
    caps = a.capabilities()
    assert "image.generate" in caps
    assert "image.upscale" in caps
    return a


@pytest.fixture(scope="module")
def conv_agent(store, history):
    return ConversationAgent(store, execution_history=history)


class TestM18RealE2E:

    def test_01_single_step_generate(self, agent, store):
        t0 = time.time()
        job = agent.run(
            capability="image.generate",
            params={"prompt": "a small red circle on white background", "negative_prompt": "", **E2E_PARAMS},
            base_url=COMFY_URL, ws_timeout=WS_TIMEOUT,
        )
        elapsed = time.time() - t0

        assert job.state == JobState.SUCCESS, f"generate FAILED: {job.error}"
        assert len(job.output_assets) >= 1
        assert job.chain_step_index is None

        asset = store.get(job.output_assets[0])
        assert asset is not None
        assert Path(asset.path).exists()
        print(f"\n  [generate] elapsed={elapsed:.1f}s asset={job.output_assets[0]}")

    def test_02_chain_generate_upscale(self, conv_agent, store, history):
        t0 = time.time()
        job = conv_agent.turn(
            session_id="e2e_chain",
            request="нарисуй синий квадрат и увеличь разрешение",
            base_url=COMFY_URL, ws_timeout=WS_TIMEOUT,
        )
        elapsed = time.time() - t0

        assert job.state == JobState.SUCCESS, f"chain FAILED: {job.error}"
        assert len(job.output_assets) >= 1

        ctx = conv_agent.context("e2e_chain")
        assert ctx.active_asset is not None
        assert ctx.dialog_state == "idle"

        for aid in ctx.assets:
            a = store.get(aid)
            assert a is not None
            assert Path(a.path).exists()

        print(f"\n  [chain] elapsed={elapsed:.1f}s active={ctx.active_asset} assets={ctx.assets}")

    def test_03_chain_step_index_in_history(self, history):
        records = history.get_attempts()
        chain_records = [r for r in records if r.chain_step_index is not None]
        assert len(chain_records) >= 2, f"chain records: {len(chain_records)}"

        indices = sorted([r.chain_step_index for r in chain_records])
        assert 0 in indices
        assert 1 in indices

        caps = {r.chain_step_index: r.capability for r in chain_records}
        print(f"\n  [history] chain_step_index -> capability: {caps}")
        assert caps[0] == "image.generate"
        assert caps[1] == "image.upscale"

    def test_04_lineage(self, store, history):
        records = history.get_attempts()
        chain_records = sorted(
            [r for r in records if r.chain_step_index is not None],
            key=lambda r: r.chain_step_index,
        )
        assert len(chain_records) >= 2

        step0 = chain_records[0]
        step1 = chain_records[1]

        # Проверяем что output_assets заполнены в ExecutionRecord
        assert step0.output_assets, f"step0.output_assets пуст"
        assert step1.output_assets, f"step1.output_assets пуст"

        asset_a_id = step0.output_assets[0]
        asset_b_id = step1.output_assets[0]

        asset_a = store.get(asset_a_id)
        asset_b = store.get(asset_b_id)
        assert asset_a, f"Asset A {asset_a_id} не найден"
        assert asset_b, f"Asset B {asset_b_id} не найден"

        size_a = Path(asset_a.path).stat().st_size
        size_b = Path(asset_b.path).stat().st_size

        print(f"\n  [lineage] A={asset_a_id} size={size_a}")
        print(f"  [lineage] B={asset_b_id} size={size_b}")

    def test_05_chain_result_success(self, conv_agent):
        ctx = conv_agent.context("e2e_chain")
        assert ctx.dialog_state == "idle"
        assert ctx.active_asset is not None

    def test_06_failure_semantics(self, conv_agent, store):
        job = conv_agent.turn(
            session_id="e2e_failure",
            request="нарисуй кота и потом сделай 3D-модель и анимируй",
            base_url=COMFY_URL, ws_timeout=WS_TIMEOUT,
        )
        ctx = conv_agent.context("e2e_failure")
        print(f"\n  [failure] dialog_state={ctx.dialog_state} job.state={job.state}")

    def test_07_cancellation_assets_preserved(self, conv_agent, store):
        ctx = conv_agent.context("e2e_chain")
        for aid in ctx.assets:
            a = store.get(aid)
            assert a is not None
            assert Path(a.path).exists()
        print(f"\n  [cancel] All {len(ctx.assets)} assets preserved")

    def test_08_single_step_regression_after_chain(self, agent):
        t0 = time.time()
        job = agent.run(
            capability="image.generate",
            params={"prompt": "a small green triangle on white background", "negative_prompt": "", **E2E_PARAMS},
            base_url=COMFY_URL, ws_timeout=WS_TIMEOUT,
        )
        elapsed = time.time() - t0

        assert job.state == JobState.SUCCESS, f"regression FAILED: {job.error}"
        assert len(job.output_assets) >= 1
        assert job.chain_step_index is None
        print(f"\n  [regression] elapsed={elapsed:.1f}s asset={job.output_assets[0]}")
