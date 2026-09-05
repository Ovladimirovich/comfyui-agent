# M25 Colab Runtime Smoke Check — Plan

**Статус:** PLAN MODE (read-only, no execution)
**Дата:** 2026-09-04
**Цель:** Проверить runtime Colab ComfyUI для M25 E2E без изменений кода

---

## 1. Существующий URL из истории

Из `engineering/CHANGELOG.md:67`:
```
https://thru-governance-overcome-ends.trycloudflare.com
Tesla T4 15.6GB
Remote E2E PROVEN (M5)
```

**Важно:** Cloudflare Tunnel временный — URL может быть неактуален.

---

## 2. Smoke Check Plan (BEZ ИЗМЕНЕНИЙ КОДА)

### Шаг 1: Доступность
```powershell
$env:COMFY_REMOTE_URL = "https://thru-governance-overcome-ends.trycloudflare.com"
python -c "
from app.comfy.client import ComfyClient
c = ComfyClient(base_url='$env:COMFY_REMOTE_URL', timeout=30)
stats = c.get_system_stats()
print('system_stats OK')
print(stats)
"
```

### Шаг 2: Object Info — Required Nodes
```python
info = c.get_object_info()
required = ["LoadImage", "ImageBatch", "VAEEncode", "KSampler", "VAEDecode", "CreateVideo", "SaveVideo"]
for n in required:
    print(f"{n}: {'PASS' if n in info else 'GAP'}")
```

### Шаг 3: Available Models
```python
checkpoints = c.discover_checkpoints()
print(f"Checkpoints: {checkpoints}")
```

### Шаг 4: Workflow Validation
```python
from app.registry.workflow import load_workflow
wf = load_workflow("workflows/video_image_to_video/manifest.json")
print(f"Status: {wf.status}")
print(f"Asset inputs: {wf.asset_inputs}")
```

---

## 3. Expected Results Matrix

| Component | Expected | If Missing |
|-----------|----------|------------|
| `/system_stats` | 200 OK | STOP — backend down |
| `LoadImage` | ✅ | FATAL — core node |
| `ImageBatch` | ✅ | **GAP REPORT** |
| `VAEEncode` | ✅ | FATAL — standard |
| `KSampler` | ✅ | FATAL — core |
| `VAEDecode` | ✅ | FATAL — core |
| `CreateVideo` | ✅ | **GAP REPORT** |
| `SaveVideo` | ✅ | **GAP REPORT** |
| Checkpoint | ≥1 | STOP — no model |

---

## 4. Decision Tree

```
IF /system_stats FAILS:
  → STOP: Colab ComfyUI недоступен
  
IF ImageBatch MISSING:
  → GAP: ImageBatch отсутствует
  → List all batch-related nodes from /object_info
  → STOP: await resolution
  
IF CreateVideo/SaveVideo MISSING:
  → GAP: VideoHelperSuite / required video nodes отсутствуют
  → STOP: await resolution
  
IF Checkpoint MISSING:
  → STOP: no model available
  
IF ALL PASS:
  → M25 COLAB RUNTIME READY
  → COMFY_REMOTE_URL = ...
  → GPU = ...
  → ComfyUI = ...
  → All nodes = PASS
  → Model = PASS
  → STOP: ready for E2E
```

---

## 5. E2E Test (готов, БЕЗ изменений)

`tests/test_m25_e2e_remote.py` — структура теста:

```python
"""M25 E2E — remote Colab chain: image.generate → image.edit → video.image_to_video"""
import os, pytest
from app.comfy.client import ComfyClient
from app.provider.comfyui import ComfyUIProvider
from app.assets.store import AssetStore
from app.conversation import ConversationAgent
from app.engine import JobState
from app.engine.experience import ExperienceStore
from app.engine.verifier import Verifier

COMFY_REMOTE_URL = os.environ.get("COMFY_REMOTE_URL")

@pytest.mark.skipif(not COMFY_REMOTE_URL, reason="COMFY_REMOTE_URL не задан")
class TestM25E2ERemote:
    @pytest.fixture(autouse=True)
    def smoke_check(self):
        client = ComfyClient(base_url=COMFY_REMOTE_URL, timeout=30)
        try:
            stats = client.get_system_stats()
        except Exception as e:
            pytest.skip(f"remote ComfyUI недоступен: {e}")
        
        info = client.get_object_info()
        for node in ["LoadImage", "VAEEncode", "KSampler", "VAEDecode", 
                     "CreateVideo", "SaveVideo", "ImageBatch"]:
            assert node in info, f"Required node '{node}' not found"
    
    def test_chain_generate_edit_video(self, tmp_path):
        store = AssetStore(root=tmp_path)
        exp_store = ExperienceStore(tmp_path / "experience")
        agent = ConversationAgent(store, experience_store=exp_store)
        
        client = ComfyClient(base_url=COMFY_REMOTE_URL, timeout=240)
        provider = ComfyUIProvider(client, backend_id="remote_comfyui")
        
        # Step 1: image.generate
        j1 = agent.turn("s1", capability="image.generate",
                       params={"prompt": "a cat", "width": 512, "height": 512, "steps": 20},
                       provider=provider, ws_timeout=360)
        assert j1.state == JobState.SUCCESS
        a1 = j1.output_assets[0]
        
        # Step 2: image.edit → Asset₂
        j2 = agent.turn("s1", capability="image.edit",
                       params={"steps": 20},
                       provider=provider, ws_timeout=360)
        assert j2.state == JobState.SUCCESS
        a2 = j2.output_assets[0]
        assert store.lineage(a2) == [store.get(a2), store.get(a1)]
        
        # Step 3: video.image_to_video (multi-asset)
        j3 = agent.turn("s1", capability="video.image_to_video",
                       params={"fps": 4, "steps": 20},
                       provider=provider, ws_timeout=600)
        assert j3.state == JobState.SUCCESS
        video = j3.output_assets[0]
        assert store.get(video).type == "video"
        
        # Verify sequence
        verifier = Verifier(store)
        seq = verifier.verify_sequence([a1, a2])
        assert seq.ok
        
        # Verify experience
        chains = exp_store.list_chains()
        assert len(chains) > 0
        exp = exp_store.get_by_chain(j3.prompt_id[:12])
        assert exp is not None
        assert exp.sequence_assets == [a1, a2]
```

---

## 6. Что НЕ делается

- ❌ Не создаётся ColabProvider
- ❌ Не создаётся новый execution path
- ❌ Не меняется workflow.json
- ❌ Не меняется manifest.json
- ❌ Не создаётся LearningEngine
- ❌ Не начинается M26
- ❌ Не меняется M1–M24

---

## 7. Жду от вас

1. **Актуальный COMFY_REMOTE_URL** (или подтверждение старого URL)
2. **Разрешение на выполнение smoke check** (Python код выше)
3. **Решение по ImageBatch** — если отсутствует, какой вариант:
   - A: Заменить в workflow.json на PixelPerfectPixels
   - B: Использовать ImageConcat из comfyui-videohelpersuite
   - C: declared_only → E2E skip
   - D: Другое

**После smoke check GREEN → запуск E2E теста → STOP.**
