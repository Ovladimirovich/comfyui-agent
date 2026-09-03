"""Semver helper (M3).

Корректное сравнение версий (числовое, не строковое):
"0.10.9" > "0.9.99", "1.2.0" < "1.10.0".

Поддерживает опциональный pre-release (-tag), но для M3 достаточно numeric core.
"""
from __future__ import annotations

import re
from typing import Tuple

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.\-]+))?$")


def parse_version(version: str) -> Tuple[int, int, int, str]:
    """Вернуть (major, minor, patch, prerelease). prerelease='' если нет."""
    if not isinstance(version, str):
        raise ValueError(f"version must be str, got {type(version).__name__}")
    m = _SEMVER_RE.match(version.strip())
    if not m:
        raise ValueError(f"Invalid semver: {version!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4) or ""


def compare_version(a: str, b: str) -> int:
    """-1 если a<b, 0 если равны, 1 если a>b (по семантике semver)."""
    ma, mi, pa, pre_a = parse_version(a)
    mb, mi_, pb, pre_b = parse_version(b)
    for x, y in ((ma, mb), (mi, mi_), (pa, pb)):
        if x != y:
            return -1 if x < y else 1
    # numeric core равны: сравниваем pre-release (нет pre > есть pre)
    if pre_a == pre_b:
        return 0
    if pre_a == "":
        return 1
    if pre_b == "":
        return -1
    return -1 if pre_a < pre_b else (1 if pre_a > pre_b else 0)


def max_version(versions: list[str]) -> str | None:
    """Вернуть максимальную версию из списка (semver-корректно) или None."""
    if not versions:
        return None
    best = versions[0]
    for v in versions[1:]:
        if compare_version(v, best) > 0:
            best = v
    return best
