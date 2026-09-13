"""
Persistence для Runtime Validator claims.

Сохраняет и загружает validated_nodes и confirmed_claims в JSON.
"""

from __future__ import annotations

import json
import os
from typing import Optional


class ClaimsPersistence:
    """Persistence для validated nodes и confirmed claims."""

    def __init__(self, data_dir: str = "app/data/knowledge"):
        self._data_dir = data_dir
        self._validated_path = os.path.join(data_dir, "validated_nodes.json")
        self._claims_path = os.path.join(data_dir, "confirmed_claims.json")
        self._validated_nodes: dict[str, bool] = {}
        self._confirmed_claims: list[dict] = []
        self._load()

    def _load(self):
        """Загружает из JSON файлов."""
        if os.path.exists(self._validated_path):
            try:
                with open(self._validated_path, 'r', encoding='utf-8') as f:
                    self._validated_nodes = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._validated_nodes = {}

        if os.path.exists(self._claims_path):
            try:
                with open(self._claims_path, 'r', encoding='utf-8') as f:
                    self._confirmed_claims = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._confirmed_claims = []

    def save(self):
        """Сохраняет в JSON файлы."""
        os.makedirs(self._data_dir, exist_ok=True)
        
        with open(self._validated_path, 'w', encoding='utf-8') as f:
            json.dump(self._validated_nodes, f, indent=2, ensure_ascii=False)
        
        with open(self._claims_path, 'w', encoding='utf-8') as f:
            json.dump(self._confirmed_claims, f, indent=2, ensure_ascii=False)

    def add_validated_node(self, node_class: str, success: bool):
        """Добавляет валидированную ноду."""
        self._validated_nodes[node_class] = success
        self.save()

    def add_confirmed_claim(self, claim: dict):
        """Добавляет подтверждённый claim."""
        # Проверяем дубликаты
        key = (claim.get("subject"), claim.get("predicate"), claim.get("object"))
        if not any(
            (c.get("subject"), c.get("predicate"), c.get("object")) == key
            for c in self._confirmed_claims
        ):
            self._confirmed_claims.append(claim)
            self.save()

    def get_validated_nodes(self) -> dict[str, bool]:
        """Возвращает словарь валидированных нод."""
        return dict(self._validated_nodes)

    def get_confirmed_claims(self) -> list[dict]:
        """Возвращает список подтверждённых claims."""
        return list(self._confirmed_claims)

    def clear(self):
        """Очищает все данные."""
        self._validated_nodes.clear()
        self._confirmed_claims.clear()
        self.save()
