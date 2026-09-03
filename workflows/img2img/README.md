# img2img (image.edit) — M6.5

Реальный ComfyUI workflow для image-to-image (редактирование входного изображения по текстовому
запросу). Реализует закрытый функциональный gap `img2img / image.edit`, необходимый для M7
Conversation Context (реальный chain-сценарий `Asset → image input → workflow → новый Asset → lineage`).

## Статус

**EXECUTABLE** — обычный `Workflow` (не `DECLARED_ONLY`). Исполняется тем же `WorkflowEngine` /
`Job` / `Verifier` / `Asset`, что и `txt2img` / `video_generate`. Никаких `ImageEngine` /
`ImageAsset` / media-ветвления в execution core (см. `PROJECT_SPEC §5`, AD-03).

## Граф (ComfyUI API format)

| node | class_type        | назначение                                  |
|------|-------------------|---------------------------------------------|
| 1    | CheckpointLoaderSimple | модель + CLIP + VAE                      |
| 2    | CLIPTextEncode    | positive prompt                             |
| 3    | CLIPTextEncode    | negative prompt                             |
| 10   | LoadImage         | **входной Asset (image)**                   |
| 11   | VAEEncode         | image → latent (контекст входного изображения) |
| 5    | KSampler          | денойз latent-образа; `denoise` по умолч. 0.6 |
| 6    | VAEDecode         | latent → image                              |
| 9    | SaveImage         | финальный результат (image)                 |

Связь `Asset → ComfyUI input` — **декларативно** через `asset_inputs` в manifest:

```json
"asset_inputs": {
  "image": {"node": "10", "field": "image", "kind": "image"}
}
```

Никакой node-id не хардкодится в `Agent` / `Engine` — привязка формируется из манифеста
(`WorkflowEngine.build_prompt`).

## AD-23 (input compatibility)

`Capability("image.edit", media_input=("image",))` — входным ассетом должен быть `image`.
`WorkflowRegistry.evaluate_compatibility` проверяет `asset_inputs[].kind` против
`{a.type}` доступных ассетов:

- `image` Asset → совместимо (`AVAILABLE`);
- `video` / `audio` Asset → `INPUT_INCOMPATIBLE` (без resize/conversion/transcoding).

## E2E

Требует живой ComfyUI (local или remote Colab) с LoadImage/VAEEncode (ядро). Без backend — тест
`tests/test_img2img_e2e.py::test_img2img_e2e_remote` делает `skip`, не fake-success.
