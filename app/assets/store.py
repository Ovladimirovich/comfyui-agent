"""AssetStore (M2) — локальное media-agnostic управление ассетами.

Ответственность M2: файл → (копия в data/assets) → Asset (registry в data/assets.jsonl).
НЕ занимается ComfyUI upload / Provider / BackendRef — это M4.
Физический файл и Asset — разные сущности; identity Asset = id (не имя файла/путь).
"""
from __future__ import annotations

import json
import mimetypes
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .types import Asset, AssetError, AssetNotFoundError, PathSecurityError, SizeLimitError

DEFAULT_MAX_UPLOAD_BYTES = 209_715_200


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_name(name: str) -> str:
    bad = '\x00\\/:*?"<>|'
    cleaned = "".join("_" if (c in bad or c in "/\\") else c for c in name)
    cleaned = os.path.basename(cleaned)
    return cleaned or "asset"


class AssetStore:
    def __init__(self, root: Optional[str] = None, max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES):
        if root is None:
            root = Path(__file__).resolve().parents[2] / "data" / "assets"
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_upload_bytes = max_upload_bytes
        self._jsonl = self.root.parent / "assets.jsonl"
        self._assets: dict[str, Asset] = {}
        self._load()

    # --- path confinement (security) ---
    def _confine(self, candidate: Path) -> Path:
        root_real = self.root.resolve()
        cand_real = candidate.resolve()
        if cand_real != root_real and root_real not in cand_real.parents:
            raise PathSecurityError(f"path escapes storage root: {candidate}")
        return cand_real

    # --- JSONL persistence ---
    def _load(self):
        if not self._jsonl.exists():
            return
        with self._jsonl.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("op") == "upsert":
                    a = Asset(**rec["asset"])
                    self._assets[a.id] = a
                elif rec.get("op") == "delete":
                    self._assets.pop(rec["id"], None)

    def _append(self, record: dict):
        with self._jsonl.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _upsert(self, asset: Asset):
        self._assets[asset.id] = asset
        self._append({"op": "upsert", "asset": asset.to_dict()})

    # --- API ---
    def ingest(self, source_path, type: str, *, mime: Optional[str] = None,
               metadata: Optional[dict] = None, role: str = "input",
               created_from: Optional[str] = None, source_asset: Optional[str] = None,
               stored_name: Optional[str] = None) -> Asset:
        """Импортировать внешний файл: скопировать в root, зарегистрировать Asset.

        AssetStore становится владельцем своей копии. identity = id (≠ имя файла).
        """
        src = Path(source_path)
        if not src.is_file():
            raise FileNotFoundError(str(src))
        size = src.stat().st_size
        if size > self.max_upload_bytes:
            raise SizeLimitError(f"file {size} bytes exceeds limit {self.max_upload_bytes}")
        if mime is None:
            mime = mimetypes.guess_type(str(src))[0]
        asset_id = uuid.uuid4().hex
        safe = stored_name or _sanitize_name(src.name)
        target_dir = self.root / asset_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = self._confine(target_dir / safe)
        shutil.copy2(src, target_path)
        asset = Asset(
            id=asset_id, type=type, path=str(target_path),
            mime=mime, metadata=metadata or {}, role=role,
            created_from=created_from, source_asset=source_asset, created_at=_now(),
        )
        self._upsert(asset)
        return asset

    def link(self, source_asset_id: str, *, type: str, role: str = "output",
              created_from: Optional[str] = None, metadata: Optional[dict] = None,
              mime: Optional[str] = None) -> Asset:
        """Создать производный Asset (новая копия файла) с lineage от source_asset."""
        src = self.get(source_asset_id)
        if src is None:
            raise AssetNotFoundError(source_asset_id)
        return self.ingest(
            src.path, type, mime=mime, metadata=metadata, role=role,
            created_from=created_from, source_asset=source_asset_id,
        )

    def get(self, asset_id: str) -> Optional[Asset]:
        return self._assets.get(asset_id)

    def exists(self, asset_id: str) -> bool:
        return asset_id in self._assets

    def delete(self, asset_id: str):
        asset = self._assets.get(asset_id)
        if asset is None:
            raise AssetNotFoundError(asset_id)
        try:
            p = Path(asset.path)
            if p.exists() and self.root.resolve() in p.resolve().parents:
                if p.is_file():
                    p.unlink()
                try:
                    p.parent.rmdir()
                except OSError:
                    pass
        except OSError:
            pass
        self._assets.pop(asset_id, None)
        self._append({"op": "delete", "id": asset_id})

    def lineage(self, asset_id: str) -> list[Asset]:
        """Вернуть цепочку ассетов от данного к самому раннему source_asset."""
        chain: list[Asset] = []
        seen: set[str] = set()
        cur = self.get(asset_id)
        while cur is not None and cur.id not in seen:
            chain.append(cur)
            seen.add(cur.id)
            cur = self.get(cur.source_asset) if cur.source_asset else None
        return chain
