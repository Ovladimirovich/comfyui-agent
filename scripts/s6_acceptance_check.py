"""S6 acceptance runtime-evidence check on REAL stored ComfyUI schemas.

Read-only by intent: refusal path must NOT execute, NOT write. Positive scan
uses ONLY the gate predicate (no transport/writes). Any assertion failure
exits non-zero.
"""
import sys

from app.agent import Agent
from app.assets.store import AssetStore
from app.knowledge.core import KnowledgeCore
from app.knowledge.runtime_validator import RuntimeValidator
from app.registry.backends import BackendCatalog, BackendSpec

STORE = "tests/__tmp_selftest_real__"
BASE_URL = "http://127.0.0.1:8188"


class SpyClient:
    """Транспорт-шпион: если что-либо попробует исполнить — зафиксирует."""

    def __init__(self):
        self.queue_calls = []
        self.history_calls = []

    def queue_prompt(self, prompt, client_id=None, extra_data=None):
        self.queue_calls.append(prompt)
        return {"prompt_id": "p-from-spy"}

    def get_history(self, prompt_id=None):
        self.history_calls.append(prompt_id)
        return {"p-from-spy": {"status": {"status_str": "success"}, "outputs": {}}}


def main():
    core = KnowledgeCore(
        data_dir="app/data/knowledge",
        runtime_validator=RuntimeValidator(comfy_client=SpyClient()),
    )
    spy_client = core._runtime_validator.comfy_client
    schemas = core.get_schemas()
    real = [n for n in ("Get Request Node", "PollinationsImageGen") if n in schemas]
    print(f"[schema] store loaded: {len(schemas)} schemas; targets present: {real}")

    from app.knowledge.queries import classify_role
    from app.synthesis.safety import classify_safety

    for nm in ("Get Request Node", "PollinationsImageGen"):
        s = schemas[nm]
        safety = classify_safety(s.python_module, s.category, nm)
        role = classify_role(s)
        print(f"[schema] {nm}: module={s.python_module!r} category={s.category!r} "
              f"safety={safety.value} role={role}")

    # Snapshot состояния до прогонов + шпионы на persistence-записи.
    validated_before = dict(core.get_validated_nodes())
    claims_before = len(core.get_confirmed_claims())
    writes = {"validated": 0, "claims": 0}

    class SpyVal:
        def __call__(self, *a, **k):
            writes["validated"] += 1

    class SpyClaim:
        def __call__(self, *a, **k):
            writes["claims"] += 1

    core._claims_persistence.add_validated_node = SpyVal()
    core._claims_persistence.add_confirmed_claim = SpyClaim()

    backends = BackendCatalog([
        BackendSpec(backend_id="local_comfyui", base_url=BASE_URL, kind="local_comfyui"),
    ])
    store = AssetStore(root=STORE)
    agent = Agent(store, knowledge_core=core, backends=backends)

    for nm in ("Get Request Node", "PollinationsImageGen"):
        res = agent.run_self_test(nm, backend_id="local_comfyui", base_url=BASE_URL)
        reasons = res["refusal_reasons"]
        ok = res["status"] == "refused" and "requires_confirmation" in reasons
        print(f"[gate]  {nm}: status={res['status']} reasons={reasons} "
              f"claim_status={res['claim_status']} => {'PASS' if ok else 'FAIL'}")
        assert ok, res
        # Повтор из кэша: тот же отказ, без повторной оценки и обращений к storage-ах.
        res2 = agent.run_self_test(nm, backend_id="local_comfyui", base_url=BASE_URL)
        assert res2["refusal_reasons"] == reasons, "cache mismatch as"
        assert res2["claim_status"] is None

    # Отказ НЕ может привести к исполнению или записям.
    assert spy_client.queue_calls == [] and spy_client.history_calls == [], \
        "transport вызван при отказе!"
    assert writes["validated"] == 0 and writes["claims"] == 0, writes
    validated_after = dict(core.get_validated_nodes())
    claims_after = len(core.get_confirmed_claims())
    assert validated_after == validated_before and claims_after == claims_before, \
        "persistence изменилась при отказе!"
    print(f"[noexec/nowrite] queue_prompt={len(spy_client.queue_calls)} "
          f"get_history={len(spy_client.history_calls)} writes={writes} "
          f"validated {len(validated_before)}->{len(validated_after)} "
          f"claims {claims_before}->{claims_after}")

    # Honest gap: какие реальные узлы в снэпшоте ПРОХОДЯТ gate (без исполнения)?
    gate_pass = []
    for nm in schemas:
        if agent._self_test_gate(nm, "local_comfyui", None, BASE_URL) == []:
            gate_pass.append(nm)
    print(f"[realschema-positive] узлов реальных, проходящих gate без отказа: "
          f"{len(gate_pass)} -> {gate_pass[:12]}")
    print("S6 REAL-SCHEMA ACCEPTANCE: OK")


if __name__ == "__main__":
    main()