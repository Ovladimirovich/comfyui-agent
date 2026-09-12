"""DiscoveryFacts — единый контракт фактов, собранных prepare() до оценки совместимости.

Источник истины: docs/EXTENDED_DISCOVERY_DESIGN.md (Steps 1-3 + §H.4 + Step 7).

DiscoveryFacts объединяет три источника фактов:
  - RuntimeInfo         (из /system_stats)
  - models              (из ModelRegistry / client.discover_checkpoints)
  - custom_nodes        (из ComfyClient.discover_custom_node_packages())

custom_nodes — map {package_name: set[node_class_names]}.
Поддерживает оба формата requirement в manifests:
  - node class name (например "SoniloTextToMusic")
  - package name (например "pollinations-byop")

Step 7: NodeSchemaStore offline fallback.
  Если live discovery не удался, пытаемся загрузить кэш из NodeSchemaStore.
  При этом custom_nodes_available остаётся False — cache = last known, не live.
  AD-18: cache НЕ превращает UNKNOWN в AVAILABLE.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.registry.runtime import RuntimeInfo


# Тип для inventory custom nodes: package_name -> set[node_class_names]
CustomNodeInventory = dict[str, set[str]]


def _custom_node_names(inventory) -> set[str]:
    """Нормализовать custom-node inventory в плоский набор имён (для проверок).

    Принимает оба формата:
      - set[str]  — legacy (плоские идентификаторы, как было в evaluate);
      - dict{package: set[class_names]} — DiscoveryFacts.custom_nodes.
    Для dict возвращает ключи (package names) + все значения (node class names),
    допуская только точные совпадения (без fuzzy).
    """
    if inventory is None:
        return set()
    if isinstance(inventory, dict):
        names: set[str] = set()
        for pkg, classes in inventory.items():
            names.add(pkg)
            if isinstance(classes, (set, list, tuple)):
                names.update(classes)
        return names
    return set(inventory)


@dataclass(frozen=True)
class DiscoveryFacts:
    """Факты о runtime, моделях и custom nodes, собранные за один call prepare().

    Поля с None / пустым set/dict означают «не удалось обнаружить», а не «отсутствует».
    Authority flags позволяют caller'у понять, какие источники доступны.

    custom_nodes_available == False означает:
      - live source недоступен (может быть заполнен из cache);
      - либо source доступен, но empty (реально нет custom nodes).
    Различить эти два случая может только caller через дополнительную логику;
    для compatibility check достаточно: empty inventory → False → UNAVAILABLE/UNKNOWN.
    """

    # --- Runtime layer -------------------------------------------------------
    runtime: Optional[RuntimeInfo] = None
    runtime_available: bool = False

    # --- Model layer ---------------------------------------------------------
    models: set[str] = field(default_factory=set)
    models_available: bool = False

    # --- Custom node layer ---------------------------------------------------
    # Map: package_name -> set[node_class_names]
    # Пример: {"pollinations-byop": {"PollinationsImageGen", ...},
    #          "nodes_sonilo":   {"SoniloTextToMusic"}}
    custom_nodes: CustomNodeInventory = field(default_factory=dict)
    custom_nodes_available: bool = False

    # --- Convenience ---------------------------------------------------------

    @property
    def has_runtime(self) -> bool:
        """True если runtime данных доступны (даже если partial)."""
        return self.runtime_available

    @property
    def has_models(self) -> bool:
        """True если models обнаружены и не пустые."""
        return self.models_available and bool(self.models)

    @property
    def has_custom_nodes(self) -> bool:
        """True если live discovery вернул non-empty inventory.

        Cache-filled inventory имеет custom_nodes_available=False,
        поэтому has_custom_nodes тоже False — это корректно для AD-18.
        """
        return self.custom_nodes_available and bool(self.custom_nodes)

    def merge(self, other: "DiscoveryFacts") -> "DiscoveryFacts":
        """Slotted merge: берём non-empty значения из other поверх self.

        Используется когда несколько источников дают partial facts —
        например, runtime из одного вызова, models из другого.
        """
        return DiscoveryFacts(
            runtime=self.runtime or other.runtime,
            runtime_available=self.runtime_available or other.runtime_available,
            models=self.models or other.models,
            models_available=self.models_available or other.models_available,
            custom_nodes=self.custom_nodes or other.custom_nodes,
            custom_nodes_available=self.custom_nodes_available
            or other.custom_nodes_available,
        )


def check_custom_node_requirement(
    requirement: str,
    inventory: CustomNodeInventory,
) -> bool:
    """Проверить, что requirement покрыт custom node inventory.

    Поддерживает два формата (backward-compatible):
      1. Node class name — точное совпадение в value-set любого пакета.
         Пример: "SoniloTextToMusic" → проверяется во всех value-sets.
      2. Package name — точное совпадение в ключах inventory.
         Пример: "pollinations-byop" → проверяется по ключу.

    Если inventory пуст (или None) — возвращает False,
    чтобы downstream логика могла поставить UNKNOWN/UNAVAILABLE.
    """
    if not inventory:
        return False
    # 1. Точное совпадение по package name (ключ inventory)
    if requirement in inventory:
        return True
    # 2. Точное совпадение по node class name (value-set любого пакета)
    for classes in inventory.values():
        if requirement in classes:
            return True
    return False


def custom_nodes_from_node_schema_store(
    data_dir: Optional[str] = None,
) -> CustomNodeInventory:
    """Построить CustomNodeInventory из существующего NodeSchemaStore кэша.

    Адаптер: NodeSchemaStore хранит {class_type: NodeSchema}, мы извлекаем
    package -> {node_class_names} mapping из python_module поля.

    Built-in modules (nodes.*, comfy_extras.*) пропускаются.
    Возвращает пустой dict если кэш отсутствует или пуст.
    """
    from app.knowledge.node_schema import NodeSchemaStore

    store = NodeSchemaStore(data_dir=data_dir)
    schemas = store.load_current()
    if not schemas:
        return {}

    inventory: CustomNodeInventory = {}
    for class_type, schema in schemas.items():
        mod = schema.python_module
        if not mod:
            continue
        parts = mod.split(".")
        for i, part in enumerate(parts):
            if part == "custom_nodes" and i + 1 < len(parts):
                pkg = parts[i + 1]
                inventory.setdefault(pkg, set()).add(class_type)
                break
            if part == "comfy_api_nodes" and i + 1 < len(parts):
                pkg = parts[i + 1]
                inventory.setdefault(pkg, set()).add(class_type)
                break
    return inventory


def checkpoints_from_node_schema_store(
    data_dir: Optional[str] = None,
) -> set[str]:
    """Извлечь список checkpoint model names из существующего NodeSchemaStore кэша.

    Источник: input_required поля 'ckpt_name' ноды 'CheckpointLoaderSimple'
    (или 'unCLIPCheckpointLoader', 'CheckpointLoader') в NodeSchemaStore.
    Варианты берутся из FieldSpec.options — это точные имена чекпоинтов,
    которые ComfyUI отображает в UI.

    Возвращает пустой set если:
      - кэш отсутствует;
      - нужная нода не найдена;
      - у поля ckpt_name нет options.

    Это last-known knowledge — аналогично custom_nodes fallback.
    models_available остаётся False после использования этого кэша.
    """
    from app.knowledge.node_schema import NodeSchemaStore

    store = NodeSchemaStore(data_dir=data_dir)
    schemas = store.load_current()
    if not schemas:
        return set()

    # Проверям несколько вариантов имени ноды загрузки чекпоинтов
    candidate_nodes = {"CheckpointLoaderSimple", "unCLIPCheckpointLoader", "CheckpointLoader"}
    for node_name in candidate_nodes:
        schema = schemas.get(node_name)
        if not schema:
            continue
        for field_spec in schema.input_required:
            if field_spec.name == "ckpt_name" and field_spec.options:
                return set(field_spec.options)

    return set()
