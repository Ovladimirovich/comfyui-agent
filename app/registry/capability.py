"""Capability Model (M3).

Capability — логическая способность системы, НЕ конкретный workflow.
Одна capability может иметь множество workflow (разные версии/бэкенды).

Источник истины: docs/PROJECT_SPEC.md, docs/04_CAPABILITY_MODEL.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator


@dataclass(frozen=True)
class Capability:
    """Декларативный контракт логической способности.

    Не содержит исполнимого кода и не знает о конкретных workflow.
    """

    id: str
    media_input: tuple[str, ...] = field(default_factory=tuple)
    media_output: str | None = None
    operation: str = ""
    description: str = ""
    default_workflow: str | None = None
    parameters: tuple[str, ...] = field(default_factory=tuple)


class CapabilityRegistry:
    """Плоский расширяемый каталог capability.

    Capability != Workflow: реестр хранит только логику способности,
    сами workflow живут в WorkflowRegistry.
    """

    def __init__(self) -> None:
        self._caps: dict[str, Capability] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        builtins = [
            Capability("image.generate", media_input=(), media_output="image",
                       operation="text-to-image", description="Генерация изображения по тексту",
                       default_workflow="txt2img"),
            Capability("image.edit", media_input=("image",), media_output="image",
                       operation="image-to-image", description="Редактирование изображения"),
            Capability("image.inpaint", media_input=("image", "mask"), media_output="image",
                       operation="inpaint", description="Дорисовка по маске"),
            Capability("image.upscale", media_input=("image",), media_output="image",
                       operation="upscale", description="Увеличение разрешения изображения"),
            Capability("video.generate", media_input=(), media_output="video",
                       operation="text-to-video", description="Генерация видео по тексту"),
            Capability("video.image_to_video", media_input=("image", "video"), media_output="video",
                       operation="image-to-video", description="Видео из изображения/видео"),
            Capability("video.upscale", media_input=("video",), media_output="video",
                       operation="upscale", description="Увеличение разрешения видео"),
            Capability("audio.generate", media_input=(), media_output="audio",
                       operation="text-to-audio", description="Генерация аудио по тексту"),
            Capability("custom.execute", media_input=(), media_output="other",
                       operation="custom", description="Произвольное исполнение"),
        ]
        for c in builtins:
            self._caps[c.id] = c

    # --- API ---------------------------------------------------------------

    def register(self, capability: Capability) -> None:
        """Расширить каталог пользовательской capability."""
        self._caps[capability.id] = capability

    def get(self, capability_id: str) -> Capability | None:
        return self._caps.get(capability_id)

    def exists(self, capability_id: str) -> bool:
        return capability_id in self._caps

    def all(self) -> list[Capability]:
        return list(self._caps.values())

    def ids(self) -> list[str]:
        return list(self._caps.keys())

    def __iter__(self) -> Iterator[Capability]:
        return iter(self._caps.values())

    def __contains__(self, capability_id: str) -> bool:
        return capability_id in self._caps

    def require(self, capability_id: str) -> Capability:
        cap = self._caps.get(capability_id)
        if cap is None:
            raise KeyError(f"Unknown capability: {capability_id}")
        return cap

    def matching(self, media_input: Iterable[str], media_output: str | None = None) -> list[Capability]:
        """Вспомогательный подбор capability по входным/выходным медиа-типам."""
        out: list[Capability] = []
        need = set(media_input)
        for cap in self._caps.values():
            if need and not need.issubset(set(cap.media_input)):
                continue
            if media_output and cap.media_output != media_output:
                continue
            out.append(cap)
        return out
