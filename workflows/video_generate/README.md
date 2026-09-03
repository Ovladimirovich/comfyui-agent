# workflows/video_generate (EXECUTABLE)

Этот каталог содержит декларативный манифест capability `video.generate` **и исполнимый**
`workflow.json`. На этапе M4 здесь был только DECLARED_ONLY манифест (media-agnostic тест);
в M6 добавлен реальный граф, и Video E2E доказан на remote Colab (Tesla T4) через Cloudflare
Tunnel → локальный Windows AssetStore.

## Назначение
- Исполнимый `video_generate` workflow (KSampler + VAEDecode + CreateVideo + SaveVideo).
- Реальный video-E2E доказан (M6); `Asset(type=video)`, `Verifier(kind=video)`.

## Контракт (обновлено M6)
- `manifest.json` — исполнимый (`declared_only` отсутствует/False), `workflow.json` присутствует.
- Такой workflow попадает в VALIDATED/AVAILABLE и исполняется тем же media-agnostic engine,
  что и `txt2img`/`audio_generate` (доказывает отсутствие image-specific coupling в ядре).
- DECLARED_ONLY-механизм (AD-27) сохранён, но применяется только для будущих capability,
  ещё не имеющих исполнимого графа.

См. `docs/PROJECT_SPEC.md` §11, §22, AD-27.
