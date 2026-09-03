"""Доменные типы Asset Layer (M2).

Media-agnostic: `Asset` — единая сущность, без ImageAsset/VideoAsset-подклассов.
`type` — семантический media-класс; `mime` — формат файла. metadata — открытый словарь.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

# Известные media-классы (расширяемо, не закрывающий список).
IMAGE = "image"
VIDEO = "video"
AUDIO = "audio"
MASK = "mask"
SEQUENCE = "sequence"
DOCUMENT = "document"
OTHER = "other"

ROLE_INPUT = "input"
ROLE_OUTPUT = "output"
ROLE_REFERENCE = "reference"


class AssetError(Exception):
    pass


class PathSecurityError(AssetError):
    """Попытка выйти за пределы разрешённого storage root."""


class SizeLimitError(AssetError):
    """Файл превышает MAX_UPLOAD_BYTES."""


class AssetNotFoundError(AssetError):
    pass


@dataclass
class Asset:
    id: str
    type: str
    path: str
    mime: Optional[str] = None
    metadata: Optional[dict] = None
    role: str = ROLE_INPUT
    created_from: Optional[str] = None
    source_asset: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)
