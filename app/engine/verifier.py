"""Verifier (M4) — проверка контракта outputs по manifest.

Источник истины: docs/08_EXECUTION_MODEL.md, треб. 8 (без if image/elif video).
Проверяет: существование Asset, type == declared kind, доступность файла.
Работает единообразно для любого media-kind (kind → Asset.type, без ветвления).

M13: добавлен verify_with_diagnostics() — structural verification с диагностикой.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from app.assets import AssetStore
from app.registry.workflow import Workflow


class VerificationError(Exception):
    pass


@dataclass
class VerificationDiagnostic:
    """Диагностический результат проверки одного output."""
    output_name: str
    ok: bool
    error_message: str | None = None
    error_class: str | None = None  # transient/permanent/verification


@dataclass
class VerificationResult:
    """Результат verify_with_diagnostics()."""
    ok: bool
    diagnostics: list[VerificationDiagnostic] = field(default_factory=list)
    error_class: str | None = None  # общий класс ошибки (если есть)

    @property
    def error_message(self) -> str | None:
        """Первая ошибка (для обратной совместимости)."""
        for d in self.diagnostics:
            if not d.ok and d.error_message:
                return d.error_message
        return None


class Verifier:
    def __init__(self, asset_store: AssetStore) -> None:
        self.store = asset_store

    def verify(self, manifest: Workflow, created_assets: dict) -> dict:
        """Проверить, что каждый declared output произведён и соответствует контракту.

        created_assets: {output_name: Asset}
        """
        for name, spec in manifest.outputs.items():
            asset = created_assets.get(name)
            if asset is None:
                raise VerificationError(f"output '{name}' не произведён")
            # контракт: тип Asset должен совпадать с declared kind
            if asset.type != spec.kind:
                raise VerificationError(
                    f"output '{name}': тип ассета {asset.type!r} != declared kind {spec.kind!r}"
                )
            if not os.path.exists(asset.path):
                raise VerificationError(f"output '{name}': файл недоступен {asset.path}")
        return created_assets

    def verify_with_diagnostics(
        self, manifest: Workflow, created_assets: dict
    ) -> VerificationResult:
        """Проверить контракт с диагностикой (M13).

        В отличие от verify(), НЕ выбрасывает исключение.
        Возвращает VerificationResult с детальной информацией по каждому output.
        """
        diagnostics: list[VerificationDiagnostic] = []
        overall_ok = True

        for name, spec in manifest.outputs.items():
            asset = created_assets.get(name)
            if asset is None:
                diagnostics.append(VerificationDiagnostic(
                    output_name=name,
                    ok=False,
                    error_message=f"output '{name}' не произведён",
                    error_class="permanent",
                ))
                overall_ok = False
                continue

            if asset.type != spec.kind:
                diagnostics.append(VerificationDiagnostic(
                    output_name=name,
                    ok=False,
                    error_message=(
                        f"output '{name}': тип ассета {asset.type!r} "
                        f"!= declared kind {spec.kind!r}"
                    ),
                    error_class="verification",
                ))
                overall_ok = False
                continue

            if not os.path.exists(asset.path):
                diagnostics.append(VerificationDiagnostic(
                    output_name=name,
                    ok=False,
                    error_message=f"output '{name}': файл недоступен {asset.path}",
                    error_class="transient",
                ))
                overall_ok = False
                continue

            # Проверка размера файла (пустой = ошибка)
            try:
                file_size = os.path.getsize(asset.path)
                if file_size == 0:
                    diagnostics.append(VerificationDiagnostic(
                        output_name=name,
                        ok=False,
                        error_message=f"output '{name}': файл пустой (0 bytes)",
                        error_class="verification",
                    ))
                    overall_ok = False
                    continue
            except OSError:
                pass

            diagnostics.append(VerificationDiagnostic(
                output_name=name,
                ok=True,
            ))

        # Общий класс ошибки
        error_class = None
        if not overall_ok:
            error_classes = [d.error_class for d in diagnostics if not d.ok and d.error_class]
            if error_classes:
                # Приоритет: permanent > verification > transient
                if "permanent" in error_classes:
                    error_class = "permanent"
                elif "verification" in error_classes:
                    error_class = "verification"
                else:
                    error_class = "transient"

        return VerificationResult(
            ok=overall_ok,
            diagnostics=diagnostics,
            error_class=error_class,
        )
