# P1 Capability Coverage Audit

**Дата:** 2026-09-07
**Метод:** Структурный анализ workflow/manifest, cached /object_info (978 схем), код WorkflowEngine/Verifier/Asset, тесты.
**ComfyUI:** НЕ запущен (connection refused). Данные из KnowledgeCore persistent store (последний successful refresh).

---

## Audit Table

| Capability | Workflow | Manifest | Real Nodes | Executable | Verifier | Asset | Tests | Status |
|---|---|---|---|---|---|---|---|---|
| image.generate | txt2img + pollinations_image (2) | Valid | All core + PollinationsImageGen | Yes (local E2E proven) | Yes | Yes | Structural + E2E (local) | **READY** |
| image.edit | img2img (1) | Valid | All core (LoadImage, VAEEncode, KSampler...) | Yes (structurally) | Yes | Yes | Structural + E2E (remote only) | **PARTIAL** |
| image.upscale | upscale (1) | Valid | ImageScale (PIL resize, lanczos) | Yes (structurally) | Yes | Yes | Structural + E2E (remote only) | **PARTIAL** ⚠️ |
| image.inpaint | — | — | Core nodes exist (see below) | No | — | — | — | **BLOCKED** |
| video.generate | video_generate (1) | Valid | All core (CreateVideo, SaveVideo) | Yes (structurally) | Yes | Yes | Structural + E2E (remote only) | **PARTIAL** |
| video.image_to_video | video_image_to_video (1) | Valid | All core + BatchImagesNode | Yes (structurally) | Yes | Yes | E2E (remote only) | **PARTIAL** |
| video.upscale | — | — | FluxVideoUpscaleNode (BFL API) | No | — | — | — | **BLOCKED** |
| audio.generate | audio_generate (1) | Valid | SoniloTextToMusic + SaveAudio | Yes (structurally) | Yes | Yes | E2E (remote only) | **PARTIAL** |
| text.generate | text_generate (1) | Valid | OpenAICompatibleChat + SaveText | Yes (structurally) | Yes | Yes | None | **PARTIAL** |
| custom.execute | — | — | — | — | — | — | — | REGISTERED_ONLY |

---

## Detailed Findings Per Capability

### 1. image.generate — READY ✅

**Workflows:** txt2img@1.0.0, pollinations_image@1.0.0

**txt2img:** CheckpointLoaderSimple → CLIPTextEncode (x2) → EmptyLatentImage → KSampler → VAEDecode → SaveImage
- Все ноды core ComfyUI (module: comfy_extras.*)
- Требует checkpoint модель
- Requires live ComfyUI

**pollinations_image:** PollinationsImageGen → SaveImage
- PollinationsImageGen: API-based, outputs (IMAGE, STRING)
- Не требует локальных моделей — работает через внешний API
- **E2E proven:** 121s SUCCESS в текущей сессии (LOCAL ComfyUI Desktop)

**Node schemas confirmed:** SaveImage ✓, PollinationsImageGen ✓, CheckpointLoaderSimple ✓, CLIPTextEncode ✓, EmptyLatentImage ✓, KSampler ✓, VAEDecode ✓

**Tests:** `test_m4_execution.py` (build_prompt unit, verifier unit, txt2img E2E, video_generate structural), `test_knowledge_s4_real_e2e.py`

---

### 2. image.edit (img2img) — PARTIAL

**Workflow:** img2img@1.0.0

**Node chain:** LoadImage → VAEEncode → KSampler → VAEDecode → SaveImage (с CLIPTextEncode x2, CheckpointLoaderSimple)
- Все ноды core ComfyUI
- asset_inputs: image (node 10, field "image", kind "image")
- Требует checkpoint + asset input (входное изображение)

**Node schemas confirmed:** LoadImage ✓, VAEEncode ✓, KSampler ✓, SaveImage ✓

**Tests:** `test_img2img_e2e.py` — requires `COMFY_REMOTE_URL` (remote Colab), skip без него
**E2E on local ComfyUI:** НЕ ПРОВЕРЕН

---

### 3. image.upscale — PARTIAL ⚠️ Semantic Mismatch

**Workflow:** upscale@1.0.0

**Node chain:** LoadImage → ImageScale (lanczos, 1024x1024) → SaveImage

**⚠️ КРИТИЧЕСКОЕ ЗАМЕЧАНИЕ:** Текущий workflow делает **PIL resize** (lanczos), а НЕ model-based upscale.

**Реальные ноды для model-based upscale (есть в schema):**
- `UpscaleModelLoader`: outputs UPSCALE_MODEL, module: comfy_extras.nodes_upscale_model
- `ImageUpscaleWithModel`: inputs (upscale_model, image), outputs IMAGE, module: comfy_extras.nodes_upscale_model

**Почему workflow использует ImageScale вместо UpscaleModelLoader:**
- ImageScale не требует моделей — работает с любым ComfyUI
- UpscaleModelLoader требует файл модели (RealESRGAN_x4plus.pth и т.п.) в папке models/upscale_models/

**Node schemas confirmed:** ImageScale ✓, UpscaleModelLoader ✓, ImageUpscaleWithModel ✓

**Tests:** `test_upscale.py` — structural + remote E2E (COMFY_REMOTE_URL)
**E2E on local ComfyUI:** НЕ ПРОВЕРЕН (тест требует COMFY_REMOTE_URL)

---

### 4. image.inpaint — BLOCKED (0 workflows)

**Capability registered:** Да — media_input=("image", "mask"), media_output="image", operation="inpaint"

**Core ComfyUI ноды для inpainting (все подтверждены в schema):**
- `LoadImageMask`: outputs MASK, module: nodes — загрузка маски
- `SetLatentNoiseMask`: inputs (samples, mask), outputs LATENT — установка маски шума
- `VAEEncodeForInpaint`: inputs (pixels, vae, mask, grow_mask_by), outputs LATENT — encodes image+mask для inpainting
- `InpaintModelConditioning`: inputs (positive, negative, vae, pixels, mask, noise_mask), outputs (CONDITIONING, CONDITIONING, LATENT) — модельная conditioning

**Partner/API ноды для inpainting (в schema):**
- `RecraftImageInpaintingNode`: outputs IMAGE (API-based)
- `FluxProFillNode`: outputs IMAGE (BFL API)
- `FluxProExpandNode`: outputs IMAGE (BFL API)

**Минимальный workflow (core nodes):**
LoadImage → VAEEncodeForInpaint → KSampler → VAEDecode → SaveImage (+ LoadImageMask для маски, CheckpointLoaderSimple)

**Workflow НЕ СОЗДАН.** Все ноды доступны. Workflow теоретически исполняем.

---

### 5. video.generate — PARTIAL

**Workflow:** video_generate@1.0.0

**Node chain:** CheckpointLoaderSimple → CLIPTextEncode (x2) → EmptyLatentImage → KSampler → VAEDecode → CreateVideo → SaveVideo
- Все ноды core ComfyUI (module: comfy_extras.nodes_video)
- CreateVideo: inputs (images, fps), outputs VIDEO
- SaveVideo: inputs (video, filename_prefix, format), outputs VIDEO
- Требует checkpoint модель

**Node schemas confirmed:** CreateVideo ✓, SaveVideo ✓ (SaveVideo — module: comfy_extras.nodes_video)

**Tests:** `test_video_e2e.py` — requires `COMFY_REMOTE_URL` (remote Colab), skip без него. `test_m4_execution.py::test_video_generate_executable` — structural only (no live ComfyUI)

**E2E on local ComfyUI:** НЕ ПРОВЕРЕН

---

### 6. video.image_to_video — PARTIAL

**Workflow:** video_image_to_video@1.0.0

**Node chain:** LoadImage → BatchImagesNode → VAEEncode → KSampler → VAEDecode → CreateVideo → SaveVideo (+ CLIPTextEncode x2, CheckpointLoaderSimple)
- BatchImagesNode: image/batch — для пакетной обработки кадров
- asset_inputs: images (node 10, field "image", kind "image")
- Требует checkpoint + входные изображения

**Node schemas confirmed:** BatchImagesNode ✓, CreateVideo ✓, SaveVideo ✓

**Tests:** `test_video_e2e.py` — requires `COMFY_REMOTE_URL`
**E2E on local ComfyUI:** НЕ ПРОВЕРЕН

---

### 7. video.upscale — BLOCKED (0 workflows)

**Capability registered:** Да — media_input=("video",), media_output="video", operation="upscale"

**Ноды в schema:**
- `FluxVideoUpscaleNode`: outputs VIDEO, module: comfy_api_nodes.nodes_bfl (BFL partner package)
  - inputs: video, upscale_factor, mode, prompt, auto_downscale, safety_tolerance, seed
  - **Требует BFL API ключ** — не локальное исполнение
- `VHS_VideoLoad` / `VHS_VideoCombine`: **НЕ В SCHEMA** — VideoHelperSuite НЕ УСТАНОВЛЕН

**Препятствия:**
- VideoHelperSuite не установлен → нет возможности загрузить/сохранить видео локально
- FluxVideoUpscaleNode требует BFL API ключ → внешний сервис
- Нет альтернативного пути для локального video upscale

**Workflow НЕ ВОЗМОЖЕН** без установки VideoHelperSuite или аналога.

---

### 8. audio.generate — PARTIAL

**Workflow:** audio_generate@1.0.0

**Node chain:** SoniloTextToMusic → SaveAudio
- SoniloTextToMusic: outputs AUDIO, module: comfy_api_nodes.nodes_sonilo (API-based)
- SaveAudio: outputs AUDIO, module: comfy_extras.nodes_audio (⚠️ category: "audio" — DEPRECATED в display_name)

**Node schemas confirmed:** SoniloTextToMusic ✓, SaveAudio ✓

**⚠️ SaveAudio отмечен как DEPRECATED** в display_name: "Save Audio (FLAC) (DEPRECATED)"

**Tests:** `test_audio_e2e.py` — requires `COMFY_REMOTE_URL` (remote Colab с SoniloTextToMusic + SaveAudio)
**E2E on local ComfyUI:** НЕ ПРОВЕРЕН

---

### 9. text.generate — PARTIAL

**Workflow:** text_generate@1.0.0 (создан в P0-3)

**Node chain:** OpenAICompatibleChat → SaveText
- OpenAICompatibleChat: outputs STRING, module: custom_nodes.comfyui-openai-compatible
  - inputs: base_url, api_key, model, prompts (required)
  - optional: system_prompt, temperature, max_tokens, timeout, seed
- SaveText: outputs (none — save to file), module: custom_nodes.nodes_text

**Node schemas confirmed:** OpenAICompatibleChat ✓, SaveText ✓

**Ограничение:** Требует LLM endpoint (fallback_proxy:20130 или аналогичный)

**Tests:** НЕТ
**E2E:** НЕ ПРОВЕРЕН

---

## P1-C: Multi-output Analysis

### Вопрос: является ли multi-output незакрытым gap?

**Нет.** Мульти-вывод уже поддерживается архитектурой.

**Доказательства:**

1. **WorkflowEngine** (`engine.py:335-365`): Итерирует `manifest.outputs.items()` и обрабатывает каждый output независимо. Нет ветвления по media-типу.

2. **Verifier** (`verifier.py:57-68`): Проверяет каждый output по declared kind из манифеста.

3. **_OUTPUT_SIGNATURES** (`engine.py:35-39`): Data-driven, поддерживает image/video/audio. Unknown kinds — generic fallback (non-empty).

4. **_first_file_list** (`engine.py:64-74`): Media-agnostic — берёт первый список файлов из node output.

5. **_validate_output_bytes** (`engine.py:216-231`): Проверяет сигнатуры per kind, generic fallback для неизвестных.

**Ни один существующий workflow не использует multi-output** (все 8 workflows имеют ровно 1 output). Архитектурно поддерживается, но не протестировано на практике.

**Вывод:** Multi-output НЕ является gap. Изменения НЕ требуются.

---

## Сводная таблица

| Статус | Количество | Capabilities |
|---|---|---|
| READY | 1 | image.generate |
| PARTIAL | 6 | image.edit, image.upscale ⚠️, video.generate, video.image_to_video, audio.generate, text.generate |
| BLOCKED | 2 | image.inpaint, video.upscale |
| REGISTERED_ONLY | 1 | custom.execute |
| NOT A GAP | 1 | multi-output (P1-C) |

---

## Рекомендации (на основе фактического аудита)

### НЕОБХОДИМО СДЕЛАТЬ

**1. image.upscale: semantic fix** (ОПЦИОНАЛЬНО)
- Заменить ImageScale (PIL resize) на UpscaleModelLoader + ImageUpscaleWithModel
- **НО:** требует наличия файла модели (RealESRGAN_x4plus.pth) в models/upscale_models/
- Проверить наличие моделей в текущем ComfyUI Desktop перед созданием workflow
- Если моделей нет — текущий ImageScale workflow.functional (resize — это валидный операция)

**2. image.inpaint workflow** (ВОЗМОЖНО)
- Все core ноды доступны: LoadImageMask, SetLatentNoiseMask, VAEEncodeForInpaint, KSampler, VAEDecode, SaveImage
- Требует checkpoint модель (как txt2img)
- Минимальный workflow: LoadImage + LoadImageMask → VAEEncodeForInpaint → KSampler → VAEDecode → SaveImage
- **НО:** нет доказательства что inpainting ноды работают на текущем ComfyUI Desktop CPU

**3. text.generate tests** (Рекомендуется)
- Текущий workflow (P0-3) не имеет тестов
- Добавить structural tests (manifest/wiring validation)

### НЕ ДЕЛАТЬ

**4. video.upscale** — BLOCKED
- VideoHelperSuite не установлен
- FluxVideoUpscaleNode требует BFL API ключ
- Создавать фиктивный workflow без реальных нод — запрещено правилами
- **Требуется:** установка VideoHelperSuite или аналога → отдельная инфраструктурная задача

**5. audio.generate E2E** — требует COMFY_REMOTE_URL
- SoniloTextToMusic — API-based нода
- SaveAudio отмечен DEPRECATED
- Нет локального E2E без remote ComfyUI

### ПЕРВЫЙ ШАГ (самый простой и полезный)

Запустить ComfyUI Desktop и выполнить E2E для PARTIAL capabilities:
- image.edit (img2img) на локальном ComfyUI
- image.upscale (текущий ImageScale workflow)
- video.generate (CreateVideo + SaveVideo)

Это даст достоверное подтверждение что 6 PARTIAL capabilities реально работают на текущем ComfyUI Desktop, а не только структурно валидны.
