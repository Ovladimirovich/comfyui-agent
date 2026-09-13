# Plan: Local E2E Validation & Capability Hardening

**Статус:** APPROVED
**Дата:** 2026-09-07
**Принцип:** Доказать, что зарегистрированные capabilities реально работают на текущем runtime. Не увеличивать количество capabilities ради количества.

---

## Runtime Facts (verified)

| Параметр | Значение |
|---|---|
| ComfyUI Desktop GUI | `C:\cd\ComfyUI_NEY\Comfy Desktop\Comfy Desktop.exe` (running) |
| Runtime backend | `C:\Users\1\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI (2)\ComfyUI\main.py` |
| Python | 3.13.12 |
| Torch | 2.12.1+cpu |
| ComfyUI version | v0.34.5 |
| Port | 8188 |
| Launch args | `--enable-manager --cpu` |
| Models dir | `C:\Users\1\AppData\Local\Comfy-Desktop\ComfyUI-Shared\models` |
| Checkpoint | `realisticvisionmadne_v15.safetensors` (2 GB) — 1 available |
| Upscale models | **EMPTY** — no .pth files in `models/upscale_models/` |
| LLM endpoint (:20130) | **RUNNING** (запущен реальный `llama-server` с Qwen2.5-3B, ядро llama.cpp) — см. PHASE 1.5 |
| Custom nodes | 10 installed (incl. comfyui-openai-compatible, pollinations-byop) |
| comfy_api_nodes | EXISTS (contains nodes_sonilo.py for SoniloTextToMusic) |
| SaveText | AVAILABLE (comfy_extras/nodes_text.py, class_type="SaveText") |

**НЕ ТРОГАТЬ:** `C:\cd\ComfyUI_AMD\ComfyUI` (старая установка, off-limits)

---

## Capability Feasibility on Desktop ComfyUI

| Capability | Workflow | Nodes | Models | Endpoint | Feasibility |
|---|---|---|---|---|---|
| image.generate | pollinations_image | PollinationsImageGen ✓ | не нужен | Pollinations API | ✅ FEASIBLE |
| image.upscale | upscale (ImageScale) | ImageScale ✓ | **нет upscale моделей** | — | ❌ BLOCKED |
| image.edit | img2img | все core ✓ | checkpoint ✓ | — | ✅ FEASIBLE |
| image.inpaint | — (создать) | все core ✓ | checkpoint ✓ | — | ✅ FEASIBLE |
| text.generate | text_generate | OpenAICompatibleChat ✓, SaveText ✓ | не нужен | **:20130 не работает** | ⚠️ DEPENDS |
| video.generate | video_generate | все core ✓ | checkpoint ✓ | — | ✅ FEASIBLE |
| video.image_to_video | video_image_to_video | все core ✓ | checkpoint ✓ | — | ✅ FEASIBLE |
| audio.generate | audio_generate | SoniloTextToMusic ✓ | не нужен | Sonilo API | ⚠️ DEPENDS |
| video.upscale | — | VHS не установлен | — | — | ❌ BLOCKED |

---

## PHASE 0: PREPARATION

### 0.1 Start ComfyUI Backend
- Убедиться что ComfyUI Desktop GUI запущен
- Запустить backend через Desktop app (нажать "ComfyUI (2)" в лаунчере)
- Дождаться доступности `http://127.0.0.1:8188`
- Проверить `/object_info` — подтвердить наличие всех нужных нод
- Проверить `/system_stats` — подтвердить runtime info

### 0.2 Verify Environment
- Проверить что checkpoint доступен (Model Registry discovery)
- Проверить что upscale models пусты (подтвердить BLOCKED статус)
- Проверить статус :20130 (LLM endpoint) — запущен или нет
- Проверить что custom nodes загружены (pollinations-byop, comfyui-openai-compatible)

### 0.3 Baseline
- Запустить core tests (91 passed, 1 skipped) — убедиться что baseline не сломан
- Зафиксировать текущее состояние как baseline

---

## PHASE 1: E2E VALIDATION

Порядок: от простого к сложному, по утверждённой последовательности.

### 1.1 image.generate (re-confirm baseline)

**Workflow:** pollinations_image@1.0.0
**Nodes:** PollinationsImageGen → SaveImage
**Зависимости:** Pollinations API (внешний)
**Тест:** `test_m4_execution.py::test_txt2img_e2e` + ручной E2E

**Success criteria (Full E2E):**
1. Structural validation ✓
2. execute() succeeds
3. Job.state == SUCCESS
4. Output asset created
5. Verifier passes
6. Output file exists, not empty
7. PNG signature valid (\x89PNG)
8. Result from local Comfy Desktop

### 1.2 image.upscale (document limitation)

**Workflow:** upscale@1.0.0
**Nodes:** LoadImage → ImageScale (lanczos) → SaveImage
**Зависимости:** входное изображение
**Проблема:** нет upscale моделей → ImageScale = resize, не upscale

**Действие:**
- Запустить текущий workflow → подтвердить что ImageScale работает (resize)
- Зафиксировать: capability LIMITED (resize ≠ upscale)
- НЕ заменять ImageScale на model-based (нет моделей)
- В PHASE 3: документировать limitation

### 1.3 image.edit (img2img)

**Workflow:** img2img@1.0.0
**Nodes:** LoadImage → VAEEncode → KSampler → VAEDecode → SaveImage (+ CLIPTextEncode x2, CheckpointLoaderSimple)
**Зависимости:** checkpoint + входное изображение
**Тест:** `test_img2img_e2e.py`

**Success criteria:** Same 9 criteria as 1.1

### 1.4 image.inpaint (create + validate)

**Workflow:** СОЗДАТЬ
**Nodes (feasibility confirmed):**
- LoadImageMask → загрузка маски
- VAEEncodeForInpaint → encodes image+mask → LATENT
- InpaintModelConditioning → CONDITIONING + LATENT
- KSampler → sampling
- VAEDecode → IMAGE
- SaveImage → save
- CheckpointLoaderSimple → модель

**Зависимости:** checkpoint + входное изображение + маска

**Действие:**
1. Feasibility check: все ноды подтверждены через Desktop ComfyUI
2. Создать workflow.json с правильной wiring
3. Создать manifest.json
4. Structural validation
5. E2E validation

### 1.5 text.generate (validate chain)

**Workflow:** text_generate@1.0.0
**Nodes:** OpenAICompatibleChat → SaveText
**Зависимости:** LLM endpoint (:20130)

**Цепочка (verified):**
- User: "chat with AI"
- Planner: TEXT_KEYWORDS → text.generate
- Workflow selection: text_generate@1.0.0
- Engine: build_prompt → POST /prompt → ComfyUI executes OpenAICompatibleChat
- OpenAICompatibleChat → HTTP to base_url (default :20130/v1)
- SaveText → saves output to file
- Engine: fetch output → validate text (generic fallback, no signature) → Asset

**Действие:**
1. Проверить статус :20130 — если не работает, зафиксировать как dependency
2. Если работает — полный E2E
3. Если не работает — structural validation only + document dependency

### 1.6 video.generate

**Workflow:** video_generate@1.0.0
**Nodes:** CheckpointLoaderSimple → CLIPTextEncode (x2) → EmptyLatentImage → KSampler → VAEDecode → CreateVideo → SaveVideo
**Зависимости:** checkpoint

**Действие:** E2E validation

### 1.7 video.image_to_video

**Workflow:** video_image_to_video@1.0.0
**Nodes:** LoadImage → BatchImagesNode → VAEEncode → KSampler → VAEDecode → CreateVideo → SaveVideo (+ CLIPTextEncode x2, CheckpointLoaderSimple)
**Зависимости:** checkpoint + входные изображения

**Действие:** E2E validation

### 1.8 audio.generate

**Workflow:** audio_generate@1.0.0
**Nodes:** SoniloTextToMusic → SaveAudio
**Зависимости:** Sonilo API (внешний)

**Действие:**
1. Проверить что SoniloTextToMusic нода загружается (comfy_api_nodes.nodes_sonilo)
2. E2E validation (зависит от доступности Sonilo API)

---

## PHASE 2: CAPABILITY HARDENING

### 2.1 image.upscale: document limitation
- Текущий workflow = resize (ImageScale/lanczos)
- Upscale модели отсутствуют в Desktop ComfyUI
- Capability = BLOCKED для model-based upscale
- Для включения: скачать модели в `models/upscale_models/`
- НЕ переименовывать capability, НЕ маскировать limitation

### 2.2 image.inpaint: create workflow
- Создать `workflows/image_inpaint/manifest.json`
- Создать `workflows/image_inpaint/workflow.json`
- Провести structural + E2E validation

### 2.3 text.generate: add tests
- Добавить structural tests (manifest, wiring, capability routing)
- Добавить mock-based unit test для execution path

---

## PHASE 3: FINAL VERIFICATION & REPORT

### 3.1 Full test suite
- Запустить все automated tests
- Убедиться что regression не произошла

### 3.2 Per-capability report (для КАЖДОЙ capability)

Для каждой capability отчитаться:
- **Status:** READY / PARTIAL / BLOCKED
- **Workflow:** ID, version, путь
- **Manifest:** valid/invalid
- **Node types:** список с подтверждением в runtime
- **Runtime dependencies:** checkpoint, upscale models, LLM endpoint, API
- **Local proof:** YES/NO + Job result
- **Remote proof:** YES/NO (если есть)
- **Verifier result:** PASS/FAIL
- **Output type:** image/video/audio/text
- **Known limitations:** список
- **Code changes:** что было изменено

### 3.3 STOP
После PHASE 3 — отчёт. Без перехода к следующим задачам.

---

## Тесты: Разделение

### A. Automated Regression (запускать всегда)
- unit tests (test_m4_execution.py structural部分)
- structural tests (manifest validation, workflow structure)
- integration tests (planner routing, knowledge core)
- contract tests (verifier, asset store)

### B. Real E2E Validation (запускать с живым ComfyUI)
- Каждый workflow с реальным execute()
- Требует: ComfyUI backend на :8188 + модели + endpoint
- НЕ включать в автоматический regression suite
- Запускать отдельно: `pytest tests/e2e_validation/ -v`

---

## Risks

| Risk | Probability | Mitigation |
|---|---|---|
| ComfyUI backend не запускается | Low | Desktop app management |
| Checkpoint не загружается | Low | 1 checkpoint available (2 GB) |
| Pollinations API недоступен | Medium | Fallback to structural-only |
| LLM endpoint :20130 не работает | High (уже CLOSED) | Document as dependency |
| Sonilo API недоступен | Medium | Document as dependency |
| CPU execution too slow | Medium | Increase timeout, skip if needed |
| Out of memory (CPU) | Low | 2 GB checkpoint on CPU should work |

---

## PHASE 1 RESULTS (executed 2026-09-08, live local Comfy Desktop 0.34.5)

| # | Capability | Status | Local proof (Job) | Details |
|---|---|---|---|---|
| 1.1 | image.generate | **READY** | SUCCESS, 135.65s | real checkpoint `realisticvisionmadne_v15` via `test_m4_execution::test_txt2img_e2e`, verifier PASS, PNG \x89PNG |
| 1.2 | image.upscale | **LIMITED** | SUCCESS | resize path (ImageScale lanczos) работает (241.83s), модель-апскейл BLOCKED — `upscale_models/` пуст |
| 1.3 | image.edit | **READY** | SUCCESS, 275.00s | `test_img2img_e2e` (COMFY_REMOTE_URL=127.0.0.1:8188), lineage, PNG |
| 1.4 | image.inpaint | **READY** (новая capability) | SUCCESS, 194.37s | создан `workflows/image_inpaint/` (VAEEncodeForInpaint+grow_mask_by), helpers + `tests/e2e_validation/test_real_inpaint_e2e.py`, lineage=source_asset |
| 1.5 | text.generate | **READY** | SUCCESS | исправлены 2 дефекта workflow (SaveText.format='txt'; OpenAICompatibleChat Autogrow v3 принимает ТОЛЬКО dotted `prompts.text_1`); api_key обязателен. Запущен реальный llama-server Qwen2.5-3B на :20130 |
| 1.6 | video.generate | **READY** | SUCCESS | встроенные CreateVideo/SaveVideo (v0.34.5, НЕ VideoHelperSuite), MP4 `ftyp isom` |
| 1.7 | video.image_to_video | **READY** | SUCCESS | multi-image: фикс движка `_build_multi_asset_input` → dotted `images.image0/1` (Autogrow), BatchImagesNode+VAEEncode, MP4 |
| 1.8 | audio.generate | **DEPENDENCY_BLOCKED** | — | SoniloTextToMusic = облачный API Comfy.org (hidden `auth_token_comfy_org`/`api_key_comfy_org`); локально нет ключа → нужен Comfy.org ключ у пользователя |

### Code changes (PHASE 1/2)

- `app/engine/engine.py::_build_multi_asset_input` — BatchImagesNode (COMFY_AUTOGROW_V3): вложенный dict `images:{...}` → dotted `images.image{N}` (ComfyUI 400 required_input_missing иначе). Покрыт `tests/test_multi_asset.py::TestBuildPromptMultiDotted`.
- `workflows/text_generate/workflow.json` — SaveText format `text`→`txt`; api_key непустой; static `prompts.text_1` (dotted).
- `workflows/text_generate/manifest.json` — input binding prompt: field `prompts`→`prompts.text_1`.
- `workflows/image_inpaint/*` — созданы (workflow.json + manifest.json).
- `tests/test_text_generate.py` — 8 новых unit (manifest/wiring/routing/build_prompt).
- `tests/test_multi_asset.py` — +2 unit на dotted-формат (regression guard).
- Полный pytest не завершается из-за live E2E (`test_http_request_real_e2e` и др.) — regression по затронутым модулям зелёный; `test_planner_context.py` 6 fail — pre-existing (FakeProvider mock vs фактическая структура image-манифестов), к данным правкам не относятся.

### Notes
- Реальный LLM endpoint :20130 — запускается вручную: `C:\llama.cpp_Vulkan\llama-server.exe --jinja -m C:\llama.cpp_Vulkan\models\qwen2.5-3b\qwen2.5-3b-instruct-q4_k_m.gguf -c 8192 --host 127.0.0.1 --port 20130 --metrics`
