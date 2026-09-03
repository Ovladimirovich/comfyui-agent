"""Debug: trace chain execution with real ComfyUI."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.conversation import ConversationAgent
from app.assets.store import AssetStore
from app.engine.chain import ExecutionChain, ChainContext, ChainState
from app.engine.history import ExecutionHistory
from app.planner.decomposer import SubTask, TaskDecomposer

COMFY_URL = "http://127.0.0.1:8188"


def main():
    store = AssetStore(root=Path("_e2e_tmp"))
    history = ExecutionHistory()
    conv = ConversationAgent(store, execution_history=history)

    # Decompose
    decomposer = TaskDecomposer()
    subtasks = decomposer.decompose("нарисуй синий квадрат и увеличь разрешение")
    print("Subtasks:")
    for i, st in enumerate(subtasks):
        print(f"  {i}: cap={st.capability} desc='{st.description}' params={st.params}")

    # Create proper ChainContext
    chain_ctx = ChainContext(session_id="debug")
    ctx = conv.session("debug")

    # Create chain with debug wrapper
    original_execute = conv._execute_chain_step

    def debug_execute(subtask, chain_ctx=chain_ctx, **kwargs):
        print(f"\n  >>> STEP: {subtask.capability} params={subtask.params}")
        try:
            job = original_execute(
                subtask=subtask,
                chain_ctx=chain_ctx,
                backend_id="local_comfyui",
                provider=None,
                base_url=COMFY_URL,
                ws_timeout=120,
            )
            print(f"  <<< RESULT: state={job.state} outputs={job.output_assets} error={job.error}")
            return job
        except Exception as e:
            print(f"  <<< EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            from app.engine.job import Job, JobState
            return Job(
                prompt_id="err",
                workflow_id="",
                version="",
                capability=subtask.capability,
                state=JobState.FAILED,
                error=str(e),
            )

    chain = ExecutionChain(
        execute_fn=debug_execute,
        history=history,
        max_attempts_per_step=1,
        on_step_complete=lambda i, step: print(f"  on_step_complete({i}): state={step.state} job={step.job.prompt_id if step.job else None}"),
    )

    t0 = time.time()
    result = chain.execute(subtasks)
    elapsed = time.time() - t0

    print(f"\n=== CHAIN RESULT ===")
    print(f"  state: {result.state}")
    print(f"  steps: {len(result.steps)}")
    print(f"  duration: {elapsed:.1f}s")
    for i, step in enumerate(result.steps):
        print(f"  Step {i}: state={step.state} job_state={step.job.state if step.job else None} error={step.error}")

    # Update context
    if chain_ctx.active_asset:
        ctx.active_asset = chain_ctx.active_asset
    ctx.dialog_state = "idle" if result.ok else "error"

    print(f"\n=== CONTEXT ===")
    print(f"  active_asset: {ctx.active_asset}")
    print(f"  assets: {ctx.assets}")
    print(f"  dialog_state: {ctx.dialog_state}")

    # History
    records = history.get_attempts()
    chain_records = [r for r in records if r.chain_step_index is not None]
    print(f"\n=== HISTORY ===")
    print(f"  total records: {len(records)}")
    print(f"  chain records: {len(chain_records)}")
    for r in chain_records:
        print(f"    idx={r.chain_step_index} cap={r.capability} state={r.state}")


if __name__ == "__main__":
    main()
