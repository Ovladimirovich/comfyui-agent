"""Quick validation of M21 real ComfyUI integration."""
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent import Agent
from app.assets.store import AssetStore
from app.engine.history import ExecutionHistory
from app.resource.gateway import ClusterGateway
from app.resource.models import BackendResource, BackendHealth
from app.resource.reconciler import Reconciler
from app.resource.models import ReconcileState, RecoveryAction


def main():
    store = AssetStore(root=Path('_m21_e2e'))
    history = ExecutionHistory()
    gw = ClusterGateway(backends=[
        BackendResource(backend_id='local_comfyui', endpoint_url='http://127.0.0.1:8188',
                        health=BackendHealth.HEALTHY),
    ])
    agent = Agent(asset_store=store, execution_history=history, gateway=gw)

    print('=== Test 1: Submit to real ComfyUI ===')
    t0 = time.time()
    job = agent.run(
        capability='image.generate',
        params={'prompt': 'a red circle', 'negative_prompt': '', 'width': 64, 'height': 64, 'steps': 3, 'seed': 42},
        base_url='http://127.0.0.1:8188',
        ws_timeout=60,
    )
    elapsed = time.time() - t0
    print(f'  State: {job.state}')
    print(f'  Prompt ID: {job.prompt_id}')
    print(f'  Backend: {job.backend_execution_identity}')
    print(f'  Elapsed: {elapsed:.1f}s')
    assert job.state.value == 'SUCCESS', f'Expected SUCCESS, got {job.state}'
    assert job.backend_execution_identity is not None, 'backend_execution_identity not set!'
    print('  PASS: backend_execution_identity set correctly')

    print('\n=== Test 2: Dispatch recorded ===')
    dispatch = history.get_dispatch(job.prompt_id)
    assert dispatch is not None, 'Dispatch not recorded!'
    assert dispatch['backend_id'] == 'local_comfyui'
    print(f'  Dispatch: backend={dispatch["backend_id"]} url={dispatch["endpoint_url"]}')
    print('  PASS: dispatch recorded in History')

    print('\n=== Test 3: Reconcile COMPLETED -> no duplicate ===')
    rec = Reconciler(gateway=gw, history=history)
    result = rec.reconcile(job.prompt_id, probe_fn=lambda pid: ReconcileState.COMPLETED)
    assert result.action == RecoveryAction.RESULT_RETURNED
    assert result.target_backend_id is None
    print(f'  Action: {result.action.value} target={result.target_backend_id}')
    print('  PASS: COMPLETED -> RESULT_RETURNED, no reroute')

    print('\n=== Test 4: Reconcile UNKNOWN -> STOP (MD-01) ===')
    result2 = rec.reconcile(job.prompt_id, probe_fn=lambda pid: ReconcileState.UNKNOWN)
    assert result2.action == RecoveryAction.NONE
    assert result2.target_backend_id is None
    assert rec.can_auto_retry(job.prompt_id) is False
    print(f'  Action: {result2.action.value} target={result2.target_backend_id} can_retry={rec.can_auto_retry(job.prompt_id)}')
    print('  PASS: UNKNOWN -> STOP, MD-01 enforced')

    print('\n=== Test 5: Persistence survives restart ===')
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        persist = f'{tmp}/history.jsonl'
        h1 = ExecutionHistory(persist_path=persist)
        h1.record_dispatch('restart-test', 'local_comfyui', 'http://127.0.0.1:8188')
        del h1  # Simulate restart

        h2 = ExecutionHistory(persist_path=persist)
        d = h2.get_dispatch('restart-test')
        assert d is not None, 'Dispatch lost after restart!'
        assert d['backend_id'] == 'local_comfyui'
        print(f'  Dispatch after restart: backend={d["backend_id"]}')
        print('  PASS: dispatch persists across restart')

    print('\n=== ALL TESTS PASSED ===')


if __name__ == '__main__':
    main()
