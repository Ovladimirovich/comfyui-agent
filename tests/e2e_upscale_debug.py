"""Debug: manually test upscale step with real ComfyUI."""
import json
import time
import urllib.request
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.assets.store import AssetStore
from app.provider.comfyui import ComfyUIProvider
from app.comfy.client import ComfyClient
from app.registry import WorkflowRegistry

COMFY_URL = "http://127.0.0.1:8188"


def main():
    store = AssetStore(root=Path("_e2e_tmp"))
    client = ComfyClient(COMFY_URL)
    provider = ComfyUIProvider(client)
    registry = WorkflowRegistry()
    registry.discover("workflows")

    # Get the asset from step 0
    asset_id = "1315f1fe1dab478496dba469fae8db55"
    asset = store.get(asset_id)
    print(f"Asset: {asset.id} type={asset.type} path={asset.path}")

    # Upload to backend
    print("Uploading...")
    t0 = time.time()
    ref = provider.upload_asset(asset)
    print(f"Upload done: {time.time()-t0:.1f}s ref={ref}")

    # Get manifest
    manifest = registry.get("upscale", "1.0.0")
    print(f"Manifest asset_inputs: {manifest.asset_inputs}")

    # Build prompt from workflow.json
    wf_path = Path(manifest.workflow_path)
    with open(wf_path) as f:
        prompt = json.load(f)
    print(f"Workflow nodes: {list(prompt.keys())}")

    # Bind asset to LoadImage node
    for role, bind in manifest.asset_inputs.items():
        print(f"Binding role={role} node={bind.node} field={bind.field}")
        node = prompt.get(str(bind.node))
        if node is None:
            print(f"  ERROR: node {bind.node} not found!")
            continue
        filename = ref.reference["filename"]
        node["inputs"][bind.field] = filename
        print(f"  Set {bind.field} = {filename}")

    # Set upscale params
    prompt["20"]["inputs"]["width"] = 256
    prompt["20"]["inputs"]["height"] = 256
    prompt["20"]["inputs"]["upscale_method"] = "lanczos"

    print(f"Final prompt: {json.dumps(prompt, indent=2)}")

    # Submit
    print("\nSubmitting prompt...")
    t0 = time.time()
    pid = provider.execute(prompt, client_id="upscale-test")
    print(f"Submitted: {pid} ({time.time()-t0:.1f}s)")

    # Poll history
    print("\nPolling /history...")
    for i in range(60):
        time.sleep(3)
        try:
            resp = urllib.request.urlopen(f"{COMFY_URL}/history/{pid}", timeout=10)
            hist = json.loads(resp.read())
        except Exception as e:
            print(f"  Poll {i+1}: error: {e}")
            continue
        if pid in hist:
            entry = hist[pid]
            status = entry.get("status", {})
            outputs = entry.get("outputs", {})
            status_str = status.get("status_str", "unknown")
            print(f"  Poll {i+1}: status={status_str} outputs={list(outputs.keys())}")
            if status_str == "error":
                msgs = status.get("messages", [])
                for mt, md in msgs:
                    if mt == "execution_error":
                        node_id = md.get("node_id", "?")
                        exc_msg = md.get("exception_message", "?")
                        print(f"    Error node {node_id}: {exc_msg}")
                print("\nRESULT: FAILED")
                return
            if outputs:
                for nid, out in outputs.items():
                    if "images" in out:
                        img = out["images"][0]
                        print(f"    Image: {img.get('filename')}")
                elapsed = time.time() - t0
                print(f"\nRESULT: SUCCESS (elapsed={elapsed:.1f}s)")
                return
        else:
            if i % 5 == 0:
                print(f"  Poll {i+1}: waiting ({time.time()-t0:.1f}s)")

    print("\nRESULT: TIMEOUT")


if __name__ == "__main__":
    main()
