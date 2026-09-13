"""Helpers for real local E2E validation (tests/e2e_validation).

Минимальные утилиты для генерации тестовых PNG (входные изображения и маски)
без внешних зависимостей (только stdlib struct/zlib). Используются отдельным
Real E2E suite, который требует живой локальный ComfyUI (127.0.0.1:8188).
"""
from __future__ import annotations

import base64
import struct
import zlib


def _chunk(ctype: bytes, data: bytes) -> bytes:
    c = ctype + data
    crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    return struct.pack(">I", len(data)) + c + crc


def make_png(
    width: int = 64,
    height: int = 64,
    fill: tuple[int, int, int] = (128, 128, 128),
    rect: tuple[int, int, int, int] | None = None,
) -> bytes:
    """Минимальный solid-color PNG (8-bit RGB).

    rect=(x0,y0,x1,y1) закрашивает прямоугольник цветом fill.
    """
    header = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    rows = bytearray()
    for y in range(height):
        rows.append(0)  # filter byte (None)
        for x in range(width):
            if rect and rect[0] <= x < rect[2] and rect[1] <= y < rect[3]:
                rows += bytes(fill)
            else:
                rows += bytes([128, 128, 128])  # neutral grey default
    idat = _chunk(b"IDAT", zlib.compress(bytes(rows)))
    return header + ihdr + idat + _chunk(b"IEND", b"")


def make_mask_png(width: int = 64, height: int = 64) -> bytes:
    """Чёрно-белая маска: чёрный фон, белый прямоугольник 32x32 в центре.

    Для LoadImageMask channel=red: 255 (white) = область инпаинта, 0 = сохранить.
    """
    return make_png(width, height, fill=(255, 255, 255), rect=(16, 16, 48, 48))


_1PX_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)
