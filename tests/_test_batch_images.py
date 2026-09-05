"""Test BatchImagesNode with real uploaded images."""
import json
import os
import tempfile
import urllib.request

URL = "https://importance-kills-attempt-configurations.trycloudflare.com"

def upload_image(path):
    import mimetypes
    import uuid
    filename = os.path.basename(path)
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    with open(path, "rb") as fh:
        data = fh.read()
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{URL}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    r = urllib.request.urlopen(req, timeout=30)
    return json.loads(r.read())


# Create dummy PNGs
tmpdir = tempfile.mkdtemp()
for name in ["test1.png", "test2.png"]:
    path = os.path.join(tmpdir, name)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

print("Uploading images...")
r1 = upload_image(os.path.join(tmpdir, "test1.png"))
r2 = upload_image(os.path.join(tmpdir, "test2.png"))
print(f"Image 1: {r1}")
print(f"Image 2: {r2}")

# Build prompt with images.image0 format
prompt = {
    "1": {"inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}, "class_type": "CheckpointLoaderSimple"},
    "2": {"inputs": {"text": "smooth animation", "clip": ["1", 1]}, "class_type": "CLIPTextEncode"},
    "4": {"inputs": {"text": "blurry", "clip": ["1", 1]}, "class_type": "CLIPTextEncode"},
    "5": {
        "inputs": {
            "seed": 0, "steps": 20, "cfg": 7.0, "sampler_name": "euler",
            "scheduler": "normal", "denoise": 0.6,
            "model": ["1", 0], "positive": ["2", 0], "negative": ["4", 0],
            "latent_image": ["12", 0],
        },
        "class_type": "KSampler",
    },
    "6": {"inputs": {"samples": ["5", 0], "vae": ["1", 2]}, "class_type": "VAEDecode"},
    "7": {"inputs": {"images": ["6", 0], "fps": 4}, "class_type": "CreateVideo"},
    "8": {"inputs": {"video": ["7", 0], "filename_prefix": "test", "format": "mp4"}, "class_type": "SaveVideo"},
    "10_m25_0": {"inputs": {"image": r1["name"]}, "class_type": "LoadImage"},
    "10_m25_1": {"inputs": {"image": r2["name"]}, "class_type": "LoadImage"},
    "11": {"inputs": {"images.image0": ["10_m25_0", 0], "images.image1": ["10_m25_1", 0]}, "class_type": "BatchImagesNode"},
    "12": {"inputs": {"pixels": ["11", 0], "vae": ["1", 2]}, "class_type": "VAEEncode"},
}

body = json.dumps({"prompt": prompt}).encode()
req = urllib.request.Request(f"{URL}/prompt", data=body, headers={"Content-Type": "application/json"}, method="POST")
try:
    r = urllib.request.urlopen(req, timeout=120)
    print(f"SUCCESS: {r.read().decode()}")
except urllib.error.HTTPError as e:
    data = e.read().decode()
    print(f"HTTP {e.code}:")
    try:
        err = json.loads(data)
        nodes = err.get("node_errors", {})
        for nid, nerr in nodes.items():
            for e in nerr.get("errors", []):
                print(f"  Node {nid}: {e}")
    except:
        print(data[:500])
