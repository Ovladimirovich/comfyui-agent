"""
NodeDocEntry + NodeDocStore — хранение и управление документацией нод ComfyUI.

NodeDocEntry — документация по одной ноде (входы, выходы, конфигурация, примеры).
NodeDocStore — JSON persistence + CRUD операции.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class NodeDocEntry:
    """Документация по ноде ComfyUI."""

    node_class: str
    """Имя класса ноды: 'Get Request Node'."""

    display_name: str
    """Отображаемое имя: 'Get Request Node'."""

    category: str
    """Категория: 'RequestNode/Get Request'."""

    purpose: str
    """Назначение: 'HTTP GET запрос'."""

    python_module: str
    """Python модуль: 'custom_nodes.ComfyUI-HttpRequestNodes'."""

    inputs_documented: dict = field(default_factory=dict)
    """Документация входов: {name: {type, required, default, description}}."""

    outputs_documented: dict = field(default_factory=dict)
    """Документация выходов: {name: {type, description}}."""

    configuration: dict = field(default_factory=dict)
    """Конфигурация: {key: description}."""

    examples: list = field(default_factory=list)
    """Примеры: [{name, description, workflow}]."""

    related_nodes: list = field(default_factory=list)
    """Связанные ноды: ['Post Request Node', 'Rest Api Node']."""

    source_file: str = ""
    """Источник документации: 'docs/node_docs/HttpRequestNodes.md'."""

    ingested_at: float = field(default_factory=time.time)
    """Время импорта (epoch)."""

    version: str = "1.0"
    """Версия документации."""

    comfyui_version: str = ""
    """Версия ComfyUI на момент импорта."""


class NodeDocStore:
    """Хранение и управление документацией нод."""

    def __init__(self, data_dir: str | None = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge")
        self._docs: dict[str, NodeDocEntry] = {}
        self._data_dir = os.path.abspath(data_dir)
        self._json_path = os.path.join(self._data_dir, "node_docs.json")
        self._load()

    def ingest_from_file(self, path: str) -> int:
        """Парсит markdown файл, возвращает количество импортированных нод."""
        from .node_doc_parser import NodeDocParser

        parser = NodeDocParser()
        entries = parser.parse_file(path)
        count = 0
        for entry in entries:
            self._docs[entry.node_class] = entry
            count += 1
        if count > 0:
            self.save()
        return count

    def ingest_from_text(self, text: str, source_file: str = "") -> list[NodeDocEntry]:
        """Парсит текст, возвращает список NodeDocEntry."""
        from .node_doc_parser import NodeDocParser

        parser = NodeDocParser()
        entries = parser.parse_text(text, source_file)
        for entry in entries:
            self._docs[entry.node_class] = entry
        if entries:
            self.save()
        return entries

    def upsert(self, entry: NodeDocEntry):
        """Добавляет или обновляет запись."""
        self._docs[entry.node_class] = entry
        self.save()

    def get_doc_for(self, node_class: str) -> Optional[NodeDocEntry]:
        """Возвращает документацию для ноды."""
        return self._docs.get(node_class)

    def get_all_docs(self) -> list[NodeDocEntry]:
        """Возвращает все документации."""
        return list(self._docs.values())

    def get_docs_by_category(self, category: str) -> list[NodeDocEntry]:
        """Возвращает ноды по категории (substring match)."""
        return [d for d in self._docs.values() if category in d.category]

    def search(self, query: str) -> list[NodeDocEntry]:
        """Поиск по назначению, имени и описаниям входов."""
        query_lower = query.lower()
        results = []
        for doc in self._docs.values():
            if query_lower in doc.purpose.lower():
                results.append(doc)
                continue
            if query_lower in doc.node_class.lower():
                results.append(doc)
                continue
            for name, info in doc.inputs_documented.items():
                if isinstance(info, dict) and query_lower in info.get("description", "").lower():
                    results.append(doc)
                    break
        return results

    def list_categories(self) -> list[str]:
        """Возвращает уникальные категории."""
        cats = set()
        for doc in self._docs.values():
            if doc.category:
                cats.add(doc.category)
        return sorted(cats)

    def count(self) -> int:
        """Количество документированных нод."""
        return len(self._docs)

    def save(self):
        """Сохраняет в JSON."""
        os.makedirs(self._data_dir, exist_ok=True)
        data = {}
        for key, entry in self._docs.items():
            data[key] = {
                "node_class": entry.node_class,
                "display_name": entry.display_name,
                "category": entry.category,
                "purpose": entry.purpose,
                "python_module": entry.python_module,
                "inputs_documented": entry.inputs_documented,
                "outputs_documented": entry.outputs_documented,
                "configuration": entry.configuration,
                "examples": entry.examples,
                "related_nodes": entry.related_nodes,
                "source_file": entry.source_file,
                "ingested_at": entry.ingested_at,
                "version": entry.version,
                "comfyui_version": entry.comfyui_version,
            }
        with open(self._json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load(self):
        """Загружает из JSON."""
        if not os.path.exists(self._json_path):
            return
        try:
            with open(self._json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, item in data.items():
                self._docs[key] = NodeDocEntry(
                    node_class=item["node_class"],
                    display_name=item["display_name"],
                    category=item["category"],
                    purpose=item["purpose"],
                    python_module=item["python_module"],
                    inputs_documented=item.get("inputs_documented", {}),
                    outputs_documented=item.get("outputs_documented", {}),
                    configuration=item.get("configuration", {}),
                    examples=item.get("examples", []),
                    related_nodes=item.get("related_nodes", []),
                    source_file=item.get("source_file", ""),
                    ingested_at=item.get("ingested_at", 0),
                    version=item.get("version", "1.0"),
                    comfyui_version=item.get("comfyui_version", ""),
                )
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Failed to load node_docs.json: {e}")
