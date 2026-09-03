"""Minimal E2E probe: submit txt2img prompt to real ComfyUI and verify output."""
import json
import time
import urllib.request
from pathlib import Path
import struct
import zlib
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.comfy.client import ComfyClient
from app.provider.comfyui import ComfyUIProvider
from app.assets.store import AssetStore

COMFY_URL = "http://127.0.0.1:8188"


def make_png(w=64, h=64):
    def chunk(typ, data):
        c = typ + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    header = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
    raw = b''
    for y in range(h):
        raw += b'\x00' + b'\xff\x00\x00' * w
    idat = chunk(b'IDAT', zlib.compress(raw))
    iend = chunk(b'IEND', b'')
    return header + ihdr + idat + iend


def main():
    client = ComfyClient(COMFY_URL)
    provider = ComfyUIProvider(client)

    # 1. Discover checkpoints
    print("=== Step 1: Discover checkpoints ===")
    try:
        cps = provider.discover_checkpoints()
        print(f"  Found: {cps[:3] if cps else 'NONE'}")
    except Exception as e:
        print(f"  ERROR: {e}")
        return

    if not cps:
        print("  No checkpoints found - cannot proceed")
        return

    # 2. Create input asset
    print("\n=== Step 2: Create input asset ===")
    tmp = Path("_e2e_tmp")
    tmp.mkdir(exist_ok=True)
    test_file = tmp / "test_input.png"
    test_file.write_bytes(make_png())
    store = AssetStore(root=tmp)
    asset = store.ingest(str(test_file), type="image", role="input")
    print(f"  Asset: {asset.id}")

    # 3. Upload to backend
    print("\n=== Step 3: Upload to backend ===")
    ref = provider.upload_asset(asset)
    print(f"  BackendRef: {ref}")

    # 4. Build and submit prompt — use workflow.json template with correct node IDs
    print("\n=== Step 4: Submit prompt ===")
    import copy
    wf_path = Path(__file__).resolve().parent.parent / "workflows" / "txt2img" / "workflow.json"
    with open(wf_path) as f:
        prompt = json.load(f)
    # Override params
    prompt["1"]["inputs"]["ckpt_name"] = cps[0]
    prompt["2"]["inputs"]["text"] = "a small red circle on white"
    prompt["3"]["inputs"]["text"] = "blurry, bad quality"
    prompt["4"]["inputs"]["width"] = 128
    prompt["4"]["inputs"]["height"] = 128
    prompt["5"]["inputs"]["seed"] = 42
    prompt["5"]["inputs"]["steps"] = 3

    t0 = time.time()
    pid = provider.execute(prompt, client_id="e2e-probe")
    print(f"  prompt_id={pid}")

    # 5. Poll /history
    print("\n=== Step 5: Poll /history ===")
    for i in range(90):
        time.sleep(3)
        try:
            resp = urllib.request.urlopen(f"{COMFY_URL}/history/{pid}", timeout=10)
            hist = json.loads(resp.read())
        except Exception as e:
            print(f"  Poll {i+1}: error reading history: {e}")
            continue

        if pid in hist:
            entry = hist[pid]
            status = entry.get("status", {})
            outputs = entry.get("outputs", {})
            status_str = status.get("status_str", "unknown")
            print(f"  Poll {i+1}: status={status_str}, outputs={list(outputs.keys())}")

            if status_str == "error":
                msgs = status.get("messages", [])
                for mt, md in msgs:
                    if mt == "execution_error" and isinstance(md, dict):
                        print(f"    Error: node {md.get('node_id')}: {md.get('exception_message')}")
                print("\n  RESULT: FAILED")
                return

            if outputs:
                for node_id, out in outputs.items():
                    if "images" in out:
                        img = out["images"][0]
                        print(f"    Image: {img.get('filename')} ({img.get('subfolder', '')})")
                elapsed = time.time() - t0
                print(f"\n  RESULT: SUCCESS (elapsed={elapsed:.1f}s)")
                return
        else:
            if i % 5 == 0:
                print(f"  Poll {i+1}: waiting... ({time.time()-t0:.1f}s elapsed)")

    print("\n  RESULT: TIMEOUT")
    return


if __name__ == "__main__":
    main()
