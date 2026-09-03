"""Доменная модель RuntimeInfo — фактическое состояние ComfyUI runtime.

M1: RuntimeInfo отражает реально обнаруженное состояние, а не предположения о машине.
Значения, которые ComfyUI не предоставляет надёжно через API (fp16 / xformers / lowvram /
comfyui_version), остаются None = UNKNOWN (не выдумываем).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class RuntimeInfo:
    accelerator: Optional[str] = None
    vram_gb: Optional[float] = None
    fp16: Optional[bool] = None
    xformers: Optional[bool] = None
    lowvram: Optional[bool] = None
    comfyui_version: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def build_runtime_info(system_stats: dict) -> RuntimeInfo:
    """Построить RuntimeInfo из ответа /system_stats.

    Не выдумываем значения, которые ComfyUI не отдаёт надёжно.
    """
    accelerator: Optional[str] = None
    vram_gb: Optional[float] = None
    devices = system_stats.get("devices") or []
    if devices:
        dev = devices[0]
        dtype = dev.get("type")
        if dtype:
            accelerator = str(dtype)
        total = dev.get("vram_total")
        if isinstance(total, (int, float)) and total > 0:
            vram_gb = round(total / (1024 ** 3), 2)
    return RuntimeInfo(
        accelerator=accelerator,
        vram_gb=vram_gb,
        fp16=None,
        xformers=None,
        lowvram=None,
        comfyui_version=None,
    )


def discover_runtime(client) -> RuntimeInfo:
    """Получить RuntimeInfo из живого ComfyUI через переданный ComfyClient."""
    return build_runtime_info(client.get_system_stats())
