"""Debug: trace upscale step in chain with detailed timing."""
import json
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.assets.store import AssetStore
from app.agent import Agent
from app.engine.chain import ExecutionChain, ChainContext, ChainState
from app.engine.history import ExecutionHistory
from app.planner.decomposer import SubTask
from app.planner.plan import PlanContext
from app.planner import HeuristicPlanner

COMFY_URL = "http://127.0.0.1:8188"


def main():
    store = AssetStore(root=Path("_e2e_tmp"))
    history = ExecutionHistory()
    agent = Agent(asset_store=store, execution_history=history)

    # Step 0: generate
    print("=== Step 0: generate ===")
    t0 = time.time()
    job0 = agent.run(
        capability="image.generate",
        params={"prompt": "a blue square", "negative_prompt": "", "width": 128, "height": 128, "steps": 3, "seed": 42},
        base_url=COMFY_URL,
        ws_timeout=60,
    )
    print(f"Step 0: state={job0.state} output={job0.output_assets} elapsed={time.time()-t0:.1f}s")
    assert job0.state.value == "SUCCESS"

    asset_id = job0.output_assets[0]
    print(f"Asset A: {asset_id}")

    # Step 1: upscale (manual, tracing each step)
    print("\n=== Step 1: upscale (traced) ===")
    chain_ctx = ChainContext(session_id="trace")
    chain_ctx.active_asset = asset_id

    subtask = SubTask(capability="image.upscale", params={})

    # 1. PlanContext
    t1 = time.time()
    active_asset_obj = store.get(chain_ctx.active_asset)
    print(f"  [1] store.get: {time.time()-t1:.1f}s type={active_asset_obj.type if active_asset_obj else None}")

    t1 = time.time()
    plan_ctx = PlanContext(
        active_asset_type=active_asset_obj.type if active_asset_obj else None,
        capabilities=tuple(agent.capabilities()),
        active_workflow=chain_ctx.workflows_used[-1] if chain_ctx.workflows_used else None,
    )
    print(f"  [1] PlanContext: {time.time()-t1:.3f}s")

    # 2. Planner
    t1 = time.time()
    planner = HeuristicPlanner()
    result = planner.plan(subtask.description, context=plan_ctx)
    capability = result.capability
    merged_params = {**subtask.params, **result.params}
    print(f"  [2] Planner: {time.time()-t1:.3f}s cap={capability} params={merged_params}")

    # 3. prepare
    t1 = time.time()
    manifest, plan, provider_obj = agent.prepare(
        capability, merged_params, provider=None, backend_id="local_comfyui", base_url=COMFY_URL,
    )
    print(f"  [3] prepare: {time.time()-t1:.1f}s manifest={manifest.id}")

    # 4. Asset resolution
    t1 = time.time()
    input_assets = {}
    required_roles = {role: ain.kind for role, ain in manifest.asset_inputs.items()}
    print(f"  [4] required_roles: {required_roles}")
    for role, kind in required_roles.items():
        if active_asset_obj and active_asset_obj.type == kind:
            input_assets[role] = chain_ctx.active_asset
            print(f"  [4] matched role={role} asset={chain_ctx.active_asset}")
            break
    print(f"  [4] input_assets: {input_assets}")

    t1 = time.time()
    bindings = agent.resolve_asset_inputs(
        input_assets, context=None, store=store, as_ids=True,
        required_roles=required_roles,
    )
    plan.asset_bindings = bindings
    print(f"  [4] resolve_asset_inputs: {time.time()-t1:.3f}s bindings={bindings}")

    # 5. Execute
    t1 = time.time()
    print(f"  [5] engine.execute starting...")
    job1 = agent.engine.execute(
        manifest, plan, provider=provider_obj,
        ws_timeout=60,
    )
    print(f"  [5] engine.execute: {time.time()-t1:.1f}s state={job1.state} output={job1.output_assets}")

    # Final
    print(f"\n=== RESULT ===")
    print(f"Step 1: state={job1.state} output={job1.output_assets} error={job1.error}")
    if job1.output_assets:
        asset_b = store.get(job1.output_assets[0])
        print(f"Asset B: {job1.output_assets[0]} path={asset_b.path if asset_b else None}")
        print(f"Asset B size: {Path(asset_b.path).stat().st_size if asset_b else 0}")
        print(f"Asset A size: {Path(store.get(asset_id).path).stat().st_size}")


if __name__ == "__main__":
    main()
