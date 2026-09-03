# M4 — Execution / Verification (plan + dependency map)

**Цель:** media-agnostic Execution Engine поверх M1–M3 на РЕАЛЬНОМ ComfyUI (треб. 1-12).
**Статус:** ✅ реализован, покрыт тестами. Реальный txt2img E2E авто-исполняется при здоровом ComfyUI; при недоступном — skip (НЕ mock).

## Dependency map (что опирается на что)

```text
M1  app/comfy/client.py  ── ComfyClient (HTTP: /system_stats, /object_info, /upload/image,
   │                        /prompt, /history, /view, /interrupt)
   │   └─ discover_checkpoints() / list_model_options()  [runtime discovery, НЕ Model Registry, треб. 12]
   │
M2  app/assets.py        ── Asset / AssetStore (media-agnostic, lineage, JSONL, security)
   │
M3  app/registry/*       ── CapabilityRegistry + WorkflowRegistry (select → SelectedCandidate)
   │                        Workflow(manifest) + OutputSpec/AssetInput/NodeBinding
   │
M4  app/provider/*       ── BackendRef + ComfyUIProvider  (Provider/Backend boundary, треб. 5)
   │                        upload_asset → POST /upload/image (multipart)
   │                        execute → POST /prompt (+client_id); get_job → /history; view → /view
   │
M4  app/engine/*         ── ExecutionPlan, Job/JobState, ComfyUIWebSocket, Verifier, WorkflowEngine
        ├─ build_prompt(manifest, plan, asset_refs)  [декларативно, БЕЗ if image/elif video, треб. 8]
        ├─ execute(manifest, plan, provider):
        │     1. asset_bindings → provider.upload_asset   (transport в Provider)
        │     2. build_prompt
        │     3. _bind_models (runtime discovery чекпоинта)  [НЕ Model Registry]
        │     4. provider.execute(prompt, client_id) → prompt_id   (Job = один POST /prompt, треб. 7)
        │     5. ComfyUIWebSocket.track(prompt_id, client_id) → {node:output}  [WS обязателен, треб. 6]
        │           └ fallback: при таймауте WS → provider.get_job → /history
        │     6. для каждого manifest.outputs: provider.view(ref) → bytes → AssetStore.ingest(
        │           type=kind, role="output", created_from=job.prompt_id, source_asset=<input>)  [lineage, M2]
        │     7. Verifier.verify(manifest, created_assets)   [контракт outputs, БЕЗ media-ветвления, треб. 10]
        └─ Verifier: Asset существует, asset.type == declared kind, файл доступен
```

## Границы (SAFE CHANGE — ничего не сломано)

```text
Execution Engine (M4) ── НЕ расширяет за пределы Execution:
   ✗ Agent / LLM / Conversation / UI не добавлены
   ✗ Model Registry не создан (модели — runtime discovery через /object_info)
   ✗ ComfyClient НЕ стал Provider/WorkflowRegistry (только HTTP-клиент)
Provider boundary (M4) ── единственная точка HTTP/asset transport (треб. 5)
```

## Архитектурные противоречия

- **Нет.** Discrepancy M3 (input_incompatible / unknown_runtime) официально внесён в
  `docs/PROJECT_SPEC.md §12`, `docs/06_WORKFLOW_MODEL.md`, `docs/14_RUNTIME_COMPATIBILITY.md` (треб. 11).
- **select на реальном железе → UNKNOWN:** ComfyUI API `/system_stats` не отдаёт `fp16`/`vram`
  достоверно (runtime.fp16=None) → compat `UNKNOWN` (корректно: UNKNOWN ≠ AVAILABLE, см. M3).
  Поэтому M4 E2E берёт манифест напрямую через `reg.get("txt2img","1.0.0")` и исполняет —
  это проверка ИСПОЛНЕНИЯ, не фильтрации (фильтрация покрыта M3-тестами).
- **video.generate** — на этапе M4 DECLARED_ONLY (треб. 10, `select` возвращал `None`); в M6 стал исполнимым (DECLARED_ONLY снят, добавлен `workflow.json`, Video E2E доказан).

## Реальный ComfyUI (треб. 3)

- Endpoints: `POST /upload/image`, `POST /prompt`, `GET /history/{pid}`, `WS /ws?client_id=…`, `GET /view`.
- WebSocket: `ws://host:port/ws?client_id=<cid>`; подписка `{"prompt_id": pid}`;
  слушает `executing(node=None)` / `executed(node,output)` / `progress` / `execution_error`.
- **Критично:** ComfyUI маршрутизирует события только при `client_id` в `/prompt` (иначе WS молчит).
- AMD APU: `vram_total=1 GB` dedicated → реальная генерация может требовать `--lowvram`; при OOM E2E skip (НЕ mock).

## Тесты (tests/test_m4_execution.py)

```text
test_build_prompt_image_and_video_generic   unit  — один build_prompt для image+video (media-agnostic)
test_verifier_pass_and_fail                 unit  — Verifier generic по kind
test_provider_upload_asset                  live  — реальный POST /upload/image → BackendRef
test_txt2img_e2e                            live  — реальный E2E (POST /prompt → WS → output Asset + lineage)
test_video_generate_executable              unit  — video_generate исполним (workflow.json, НЕ DECLARED_ONLY)
```
При недоступном ComfyUI все live-тесты skip (НЕ mock). Полный прогон: M1 8 / M2 10+1 / M3 25 / M4 5 = 48 passed, 1 skipped (на здоровом ComfyUI).

## REVIEW_PROTOCOL (выполнен)

```text
[✓] M4 не расширен за пределы Execution
[✓] ComfyClient не стал Provider/Registry
[✓] Реальный ComfyUI (E2E на живой модели; mock запрещён)
[✓] WorkflowEngine декларативен (build_prompt по manifest, нет if image/elif video)
[✓] Asset transport в Provider boundary
[✓] WebSocket обязателен (track через WS; /history — fallback)
[✓] Job = один POST /prompt
[✓] Verification по manifest.outputs (generic, без media-ветвления)
[✓] Lineage через M2 (created_from=Job, source_asset)
[✓] video_generate — media-agnostic contract (в M6 стал исполнимым, E2E доказан)
[✓] Discrepancy M3 закрыт (input_incompatible/unknown_runtime в docs)
[✓] Модели через /object_info runtime discovery (НЕ Model Registry)
[✓] M4 plan + dependency map (этот файл)
[✓] Тесты проходят; документация актуальна
```
