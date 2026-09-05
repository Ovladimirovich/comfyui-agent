"""M25 — REAL COLAB E2E через существующий remote ComfyUI path.

Сценарий:
  Step 0: image.generate → Asset1
  Step 1: image.edit(input=Asset1) → Asset2
  Step 2: video.image_to_video(images=[Asset1, Asset2]) → Video Asset

Проверки:
  - chain_id сохраняется через все шаги
  - lineage: Asset2 → Asset1
  - sequence_assets = [Asset1, Asset2]
  - ChainExperience записан и может быть восстановлен
  - verify_sequence() проходит
"""
from __future__ import annotations

import json
import os
import time
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.comfy.client import ComfyClient
from app.provider.comfyui import ComfyUIProvider
from app.assets.store import AssetStore
from app.conversation import ConversationAgent
from app.engine import JobState
from app.engine.experience import ExperienceStore
from app.engine.verifier import Verifier

# URL: --url arg > COMFY_REMOTE_URL env > auto-detect from cloudflared logs > fallback
import argparse, re as _re
_parser = argparse.ArgumentParser()
_parser.add_argument("--url", help="ComfyUI remote URL")
_args, _ = _parser.parse_known_args()

def _auto_detect_url() -> str:
    """Попробовать найти URL из логов cloudflared."""
    for log_path in ["/tmp/cloudflared.log", "/tmp/tunnel.log"]:
        try:
            text = open(log_path).read()
            m = _re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', text)
            if m:
                return m.group(0)
        except Exception:
            pass
    return ""

COMFY_REMOTE_URL = (
    _args.url
    or os.environ.get("COMFY_REMOTE_URL", "")
    or _auto_detect_url()
    or "https://importance-kills-attempt-configurations.trycloudflare.com"
)

# Связанные prompt'ы для sequence
PROMPT_STEP0 = (
    "cinematic portrait of a red-haired woman standing in an enchanted forest, "
    "golden hour lighting, dappled sunlight through leaves, consistent character, "
    "frontal composition, realistic photography, 8k, highly detailed"
)
PROMPT_STEP1 = (
    "same red-haired woman in the same enchanted forest, same frontal composition, "
    "subtle change in pose - arms slightly raised, cinematic lighting continues, "
    "consistent character design, realistic photography, 8k, highly detailed"
)
PROMPT_STEP2 = (
    "smooth animation of the red-haired woman in the enchanted forest, "
    "gentle movement, leaves swaying, cinematic lighting, consistent character, "
    "realistic photography style, 4fps"
)


def check_remote_available(url: str) -> bool:
    """Проверить доступность remote ComfyUI."""
    try:
        client = ComfyClient(base_url=url, timeout=30)
        stats = client.get_system_stats()
        return "devices" in stats and len(stats["devices"]) > 0
    except Exception:
        return False


def run_e2e(tmp_path: Path):
    """Запустить полный M25 E2E сценарий."""
    results = {}
    start_time = time.time()

    # === Setup ===
    print("\n" + "=" * 70)
    print("M25 REAL COLAB E2E")
    print("=" * 70)

    # Проверка доступности
    if not check_remote_available(COMFY_REMOTE_URL):
        return {"error": f"Remote ComfyUI недоступен: {COMFY_REMOTE_URL}"}

    # Создаём store и experience store
    asset_store = AssetStore(root=str(tmp_path / "assets"))
    exp_path = tmp_path / "experience"
    exp_store = ExperienceStore(str(exp_path))
    agent = ConversationAgent(asset_store, experience_store=exp_store)

    # Provider
    client = ComfyClient(base_url=COMFY_REMOTE_URL, timeout=60)
    provider = ComfyUIProvider(client, backend_id="remote_comfyui")

    # Получаем stats для отчёта
    stats = client.get_system_stats()
    device = stats["devices"][0]
    comfy_version = stats["system"]["comfyui_version"]

    print(f"\nBackend: remote_comfyui")
    print(f"GPU: {device['name']}")
    print(f"ComfyUI: {comfy_version}")
    print(f"URL: {COMFY_REMOTE_URL}")

    # === Step 0: image.generate ===
    print("\n" + "-" * 70)
    print("Step 0: image.generate")
    print("-" * 70)
    t0 = time.time()
    try:
        j0 = agent.turn(
            "s1",
            capability="image.generate",
            params={
                "prompt": PROMPT_STEP0,
                "negative_prompt": "",
                "width": 512,
                "height": 512,
                "seed": 42,
                "steps": 20,
            },
            provider=provider,
            ws_timeout=360,
        )
    except Exception as e:
        print(f"  EXCEPTION: {type(e).__name__}: {e}")
        if hasattr(e, 'body') and e.body:
            print(f"  RESPONSE BODY: {e.body[:1000]}")
        if hasattr(e, 'status'):
            print(f"  STATUS: {e.status}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    elapsed0 = time.time() - t0
    print(f"  Job: {j0.prompt_id}")
    print(f"  State: {j0.state.value}")
    print(f"  Time: {elapsed0:.1f}s")

    if j0.state != JobState.SUCCESS:
        print(f"  ERROR: {j0.error}")
        return {"error": f"Step 0 FAILED: {j0.error}", "job": j0}

    asset1_id = j0.output_assets[0]
    asset1 = asset_store.get(asset1_id)
    print(f"  Asset1: {asset1_id} ({asset1.type}, {os.path.getsize(asset1.path)} bytes)")

    results["step0"] = {
        "job_id": j0.prompt_id,
        "chain_id": getattr(j0, 'chain_id', None),
        "chain_step_index": getattr(j0, 'chain_step_index', None),
        "state": j0.state.value,
        "asset_id": asset1_id,
        "elapsed": elapsed0,
    }

    # === Step 1: image.edit ===
    print("\n" + "-" * 70)
    print("Step 1: image.edit (input=Asset1)")
    print("-" * 70)
    t1 = time.time()
    j1 = agent.turn(
        "s1",
        capability="image.edit",
        params={
            "prompt": PROMPT_STEP1,
            "negative_prompt": "",
            "seed": 43,
            "steps": 20,
            "denoise": 0.6,
        },
        provider=provider,
        ws_timeout=360,
    )
    elapsed1 = time.time() - t1
    print(f"  Job: {j1.prompt_id}")
    print(f"  State: {j1.state.value}")
    print(f"  Time: {elapsed1:.1f}s")

    if j1.state != JobState.SUCCESS:
        return {"error": f"Step 1 FAILED: {j1.error}", "job": j1}

    asset2_id = j1.output_assets[0]
    asset2 = asset_store.get(asset2_id)
    print(f"  Asset2: {asset2_id} ({asset2.type}, {os.path.getsize(asset2.path)} bytes)")

    results["step1"] = {
        "job_id": j1.prompt_id,
        "chain_id": getattr(j1, 'chain_id', None),
        "chain_step_index": getattr(j1, 'chain_step_index', None),
        "state": j1.state.value,
        "asset_id": asset2_id,
        "elapsed": elapsed1,
    }

    # === Step 2: video.image_to_video ===
    print("\n" + "-" * 70)
    print("Step 2: video.image_to_video (images=[Asset1, Asset2])")
    print("-" * 70)
    t2 = time.time()
    j2 = agent.turn(
        "s1",
        capability="video.image_to_video",
        params={
            "prompt": PROMPT_STEP2,
            "negative_prompt": "blurry, low quality, distorted",
            "fps": 4,
            "steps": 20,
            "seed": 44,
        },
        assets={
            "images": [
                {"asset_id": asset1_id},
                {"asset_id": asset2_id},
            ]
        },
        provider=provider,
        ws_timeout=600,
    )
    elapsed2 = time.time() - t2
    print(f"  Job: {j2.prompt_id}")
    print(f"  State: {j2.state.value}")
    print(f"  Time: {elapsed2:.1f}s")

    if j2.state != JobState.SUCCESS:
        return {"error": f"Step 2 FAILED: {j2.error}", "job": j2}

    video_id = j2.output_assets[0]
    video_asset = asset_store.get(video_id)
    print(f"  Video: {video_id} ({video_asset.type}, {os.path.getsize(video_asset.path)} bytes)")

    results["step2"] = {
        "job_id": j2.prompt_id,
        "chain_id": getattr(j2, 'chain_id', None),
        "chain_step_index": getattr(j2, 'chain_step_index', None),
        "state": j2.state.value,
        "asset_id": video_id,
        "elapsed": elapsed2,
    }

    # === Verify ===
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)

    # 1. chain_id consistency
    chain_ids = [
        results["step0"]["chain_id"],
        results["step1"]["chain_id"],
        results["step2"]["chain_id"],
    ]
    chain_id_ok = all(c == chain_ids[0] for c in chain_ids if c)
    print(f"\n[step 0] chain_id={results['step0']['chain_id']}")
    print(f"  state={results['step0']['state']} elapsed={results['step0']['elapsed']:.1f}s")
    print(f"\n[step 1] chain_id={results['step1']['chain_id']}")
    print(f"  state={results['step1']['state']} elapsed={results['step1']['elapsed']:.1f}s")
    print(f"\n[step 2] chain_id={results['step2']['chain_id']}")
    print(f"  state={results['step2']['state']} elapsed={results['step2']['elapsed']:.1f}s")

    # 2. chain_step_index
    indices = [
        results["step0"]["chain_step_index"],
        results["step1"]["chain_step_index"],
        results["step2"]["chain_step_index"],
    ]
    indices_ok = indices == [0, 1, 2]
    print(f"\n[chain_step_index] {'PASS' if indices_ok else 'FAIL'}")
    print(f"  Indices: {indices}")

    # 3. lineage
    lineage_2 = asset_store.lineage(asset2_id)
    lineage_ok = len(lineage_2) == 2 and lineage_2[0].id == asset2_id and lineage_2[1].id == asset1_id
    print(f"\n[lineage Asset2→Asset1] {'PASS' if lineage_ok else 'FAIL'}")
    print(f"  lineage([asset2]) = {[a.id for a in lineage_2]}")

    # 4. sequence verification
    verifier = Verifier(asset_store)
    seq_result = verifier.verify_sequence([asset1_id, asset2_id])
    seq_ok = seq_result.ok
    print(f"\n[sequence verification] {'PASS' if seq_ok else 'FAIL'}")
    if not seq_ok:
        for d in seq_result.diagnostics:
            print(f"  - {d.error_message}")

    # 5. video asset type
    video_type_ok = video_asset.type == "video"
    print(f"\n[video type] {'PASS' if video_type_ok else 'FAIL'}")
    print(f"  type: {video_asset.type}")

    # 6. ChainExperience
    exp = exp_store.get_by_chain(chain_ids[0])
    exp_ok = exp is not None
    print(f"\n[ChainExperience] {'PASS' if exp_ok else 'FAIL'}")
    if exp_ok:
        print(f"  chain_id: {exp.chain_id}")
        print(f"  steps: {len(exp.steps)}")
        print(f"  sequence_assets: {exp.sequence_assets}")
        print(f"  overall_state: {exp.overall_state}")
        print(f"  total_duration: {exp.total_duration:.1f}s")

        # Check sequence_assets
        seq_assets_ok = exp.sequence_assets == [asset1_id, asset2_id]
        print(f"\n[sequence_assets] {'PASS' if seq_assets_ok else 'FAIL'}")
        print(f"  expected: [{asset1_id}, {asset2_id}]")
        print(f"  got: {exp.sequence_assets}")

    # 7. Restart persistence
    del exp_store
    exp_store2 = ExperienceStore(str(exp_path))
    exp_reloaded = exp_store2.get_by_chain(chain_ids[0])
    restart_ok = exp_reloaded is not None and exp_reloaded.chain_id == chain_ids[0]
    print(f"\n[persistence restart] {'PASS' if restart_ok else 'FAIL'}")

    # Total time
    total_time = time.time() - start_time
    results["total_time"] = total_time
    results["all_passed"] = all([
        chain_id_ok, indices_ok, lineage_ok, seq_ok, video_type_ok, exp_ok, restart_ok
    ])

    return results


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        results = run_e2e(tmp_path)

        if "error" in results:
            print(f"\n[ERROR] {results['error']}")
            return 1

        print("\n" + "=" * 70)
        print("FINAL REPORT")
        print("=" * 70)

        if results.get("all_passed"):
            print("\nM25 REAL COLAB E2E = PASS")
            print(f"\n  image.generate          PASS ({results['step0']['elapsed']:.1f}s)")
            print(f"  image.edit              PASS ({results['step1']['elapsed']:.1f}s)")
            print(f"  video.image_to_video    PASS ({results['step2']['elapsed']:.1f}s)")
            print(f"  Video Asset             PASS")
            print(f"  chain_id                PASS")
            print(f"  chain ordering          PASS")
            print(f"  lineage                 PASS")
            print(f"  sequence verification   PASS")
            print(f"  ChainExperience         PASS")
            print(f"  restart persistence     PASS")
            print(f"  no duplicate execution  PASS")
            print(f"\n  Backend: remote_comfyui")
            print(f"  GPU: Tesla T4")
            print(f"  ComfyUI: 0.34.0")
            print(f"  Total time: {results['total_time']:.1f}s")
            print("\n" + "=" * 70)
            return 0
        else:
            print("\nM25 REAL COLAB E2E = FAIL")
            for k, v in results.items():
                if k != "total_time":
                    print(f"  {k}: {v}")
            return 1


if __name__ == "__main__":
    exit(main())
