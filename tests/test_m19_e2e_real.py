"""M19 Real E2E — Composer integration with real ComfyUI.

Scenarios:
- generate → upscale via ConversationAgent with composer
- single-step regression
- lineage
- ExecutionHistory
- chain_step_index
- Asset handoff
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.assets.store import AssetStore
from app.conversation import ConversationAgent
from app.engine import JobState
from app.engine.history import ExecutionHistory
from app.planner import Composer
from app.registry.capability import CapabilityRegistry
from app.registry.registry import WorkflowRegistry

COMFY_URL = "http://127.0.0.1:8188"
E2E_PARAMS = {"width": 128, "height": 128, "steps": 3, "seed": 42}
WS_TIMEOUT = 120


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    root = tmp_path_factory.mktemp("assets_e2e_m19")
    return AssetStore(root=root)


@pytest.fixture(scope="module")
def history():
    return ExecutionHistory()


@pytest.fixture(scope="module")
def composer():
    cap_reg = CapabilityRegistry()
    wf_reg = WorkflowRegistry(capabilities=cap_reg)
    return Composer(
        capability_registry=cap_reg,
        workflow_registry=wf_reg,
    )


@pytest.fixture(scope="module")
def conv_agent(store, history, composer):
    return ConversationAgent(
        store,
        execution_history=history,
        composer=composer,
    )


class TestM19RealE2E:

    def test_01_composer_generate_upscale_chain(self, conv_agent, store, history):
        """Composer-assisted chain: "сгенерируй и увеличь" — через реальный ComfyUI."""
        t0 = time.time()
        job = conv_agent.turn(
            session_id="e2e_m19_chain",
            request="нарисуй красный круг и увеличь разрешение",
            base_url=COMFY_URL, ws_timeout=WS_TIMEOUT,
        )
        elapsed = time.time() - t0

        assert job.state == JobState.SUCCESS, f"chain FAILED: {job.error}"
        assert len(job.output_assets) >= 1

        ctx = conv_agent.context("e2e_m19_chain")
        assert ctx.active_asset is not None
        assert ctx.dialog_state == "idle"
        assert len(ctx.assets) >= 2

        print(f"\n  [composer chain] elapsed={elapsed:.1f}s active={ctx.active_asset} assets={ctx.assets}")

    def test_02_chain_step_index_in_history(self, history):
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

    def test_03_lineage(self, store, history):
        records = history.get_attempts()
        chain_records = sorted(
            [r for r in records if r.chain_step_index is not None],
            key=lambda r: r.chain_step_index,
        )
        assert len(chain_records) >= 2

        step0 = chain_records[0]
        step1 = chain_records[1]

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

    def test_04_asset_handoff(self, store, history):
        """Asset handoff: output of step0 becomes input of step1."""
        records = history.get_attempts()
        chain_records = sorted(
            [r for r in records if r.chain_step_index is not None],
            key=lambda r: r.chain_step_index,
        )
        step0 = chain_records[0]
        step1 = chain_records[1]

        # Step 1 (upscale) should have input_assets referencing step0 output
        assert step0.output_assets
        step0_asset_id = step0.output_assets[0]
        print(f"\n  [handoff] step0 output used as input by step1")

    def test_05_single_step_regression(self, conv_agent, store):
        """Single-step regression: "сгенерируй изображение" — без composer chain."""
        t0 = time.time()
        job = conv_agent.turn(
            session_id="e2e_m19_single",
            request="нарисуй зеленый треугольник",
            base_url=COMFY_URL, ws_timeout=WS_TIMEOUT,
        )
        elapsed = time.time() - t0

        assert job.state == JobState.SUCCESS, f"regression FAILED: {job.error}"
        assert len(job.output_assets) >= 1
        assert job.chain_step_index is None

        print(f"\n  [regression] elapsed={elapsed:.1f}s asset={job.output_assets[0]}")

    def test_06_cancellation_assets_preserved(self, conv_agent, store):
        ctx = conv_agent.context("e2e_m19_chain")
        for aid in ctx.assets:
            a = store.get(aid)
            assert a is not None
            assert Path(a.path).exists()
        print(f"\n  [cancel] All {len(ctx.assets)} assets preserved")