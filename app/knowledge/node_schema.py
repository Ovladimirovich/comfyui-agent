"""NodeSchema — runtime contract node. ТОЛЬКО интерфейс, без семантики.

NodeSchemaStore — persistence snapshot'ов /object_info.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass(frozen=True)
class FieldSpec:
    """Спецификация одного input/output поля node."""

    name: str
    type: str
    required: bool
    default: Optional[str | int | float | bool] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    options: tuple[str, ...] = ()
    tooltip: str = ""

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "type": self.type,
            "required": self.required,
        }
        if self.default is not None:
            d["default"] = self.default
        if self.min_val is not None:
            d["min_val"] = self.min_val
        if self.max_val is not None:
            d["max_val"] = self.max_val
        if self.options:
            d["options"] = list(self.options)
        if self.tooltip:
            d["tooltip"] = self.tooltip
        return d

    @classmethod
    def from_dict(cls, data: dict) -> FieldSpec:
        return cls(
            name=data["name"],
            type=data["type"],
            required=data["required"],
            default=data.get("default"),
            min_val=data.get("min_val"),
            max_val=data.get("max_val"),
            options=tuple(data.get("options", [])),
            tooltip=data.get("tooltip", ""),
        )


@dataclass(frozen=True)
class NodeSchema:
    """Runtime-контракт node. ТОЛЬКО интерфейс, без семантики."""

    class_type: str
    display_name: str
    category: str
    input_required: tuple[FieldSpec, ...]
    input_optional: tuple[FieldSpec, ...]
    output_types: tuple[str, ...]
    output_names: tuple[str, ...]
    python_module: str
    discovered_at: float
    source: str = "runtime:/object_info"

    def to_dict(self) -> dict:
        return {
            "class_type": self.class_type,
            "display_name": self.display_name,
            "category": self.category,
            "input_required": [f.to_dict() for f in self.input_required],
            "input_optional": [f.to_dict() for f in self.input_optional],
            "output_types": list(self.output_types),
            "output_names": list(self.output_names),
            "python_module": self.python_module,
            "discovered_at": self.discovered_at,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> NodeSchema:
        input_required = tuple(FieldSpec.from_dict(f) for f in data.get("input_required", []))
        input_optional = tuple(FieldSpec.from_dict(f) for f in data.get("input_optional", []))
        return cls(
            class_type=data["class_type"],
            display_name=data.get("display_name", ""),
            category=data.get("category", ""),
            input_required=input_required,
            input_optional=input_optional,
            output_types=tuple(data.get("output_types", [])),
            output_names=tuple(data.get("output_names", [])),
            python_module=data.get("python_module", ""),
            discovered_at=data.get("discovered_at", 0.0),
            source=data.get("source", "runtime:/object_info"),
        )


def parse_field_spec(name: str, raw_spec: list) -> FieldSpec:
    """Parse one field spec from /object_info format.

    ComfyUI format: [type_string, {options_dict}] or [list_of_values, {options_dict}]
    """
    if not isinstance(raw_spec, list) or len(raw_spec) < 1:
        return FieldSpec(name=name, type="UNKNOWN", required=True)

    type_part = raw_spec[0]
    meta = raw_spec[1] if len(raw_spec) > 1 and isinstance(raw_spec[1], dict) else {}

    # ENUM-like: first element is a list of string values
    if isinstance(type_part, list):
        options = tuple(str(v) for v in type_part)
        default_val = meta.get("default")
        tooltip = meta.get("tooltip", "")
        return FieldSpec(
            name=name,
            type="ENUM",
            required=True,
            default=default_val,
            options=options,
            tooltip=tooltip,
        )

    # Type string: "STRING", "IMAGE", "FLOAT", "INT", etc.
    type_str = str(type_part)
    default_val = meta.get("default")
    tooltip = meta.get("tooltip", "")
    min_val = meta.get("min")
    max_val = meta.get("max")

    return FieldSpec(
        name=name,
        type=type_str,
        required=True,
        default=default_val,
        min_val=min_val,
        max_val=max_val,
        tooltip=tooltip,
    )


def parse_optional_field(name: str, raw_spec: list) -> FieldSpec:
    """Parse one optional field spec from /object_info format."""
    field = parse_field_spec(name, raw_spec)
    return FieldSpec(
        name=field.name,
        type=field.type,
        required=False,
        default=field.default,
        min_val=field.min_val,
        max_val=field.max_val,
        options=field.options,
        tooltip=field.tooltip,
    )


def node_schema_from_object_info(class_type: str, node_data: dict) -> NodeSchema:
    """Build NodeSchema from /object_info entry for a single node."""
    display_name = node_data.get("display_name", class_type)
    category = node_data.get("category", "")
    python_module = node_data.get("python_module", "")

    input_data = node_data.get("input", {})
    if isinstance(input_data, dict):
        raw_required = input_data.get("required", {})
        raw_optional = input_data.get("optional", {})
    else:
        raw_required = {}
        raw_optional = {}

    input_required = tuple(parse_field_spec(k, v) for k, v in raw_required.items() if isinstance(v, list))
    input_optional = tuple(parse_optional_field(k, v) for k, v in raw_optional.items() if isinstance(v, list))

    output_types = tuple(node_data.get("output", []))
    output_names = tuple(node_data.get("output_name", []))

    return NodeSchema(
        class_type=class_type,
        display_name=display_name,
        category=category,
        input_required=input_required,
        input_optional=input_optional,
        output_types=output_types,
        output_names=output_names,
        python_module=python_module,
        discovered_at=time.time(),
    )


class NodeSchemaStore:
    """Persistence snapshot'ов /object_info. JSON-based."""

    def __init__(self, data_dir: str | None = None) -> None:
        if data_dir is None:
            data_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "data", "knowledge"
            )
        self._data_dir = data_dir
        self._current_path = os.path.join(data_dir, "node_schemas.json")
        self._previous_path = os.path.join(data_dir, "node_schemas_prev.json")
        os.makedirs(data_dir, exist_ok=True)

    def save_snapshot(self, schemas: dict[str, NodeSchema]) -> None:
        """Save current snapshot. Rotate previous."""
        if os.path.exists(self._current_path):
            if os.path.exists(self._previous_path):
                os.remove(self._previous_path)
            os.rename(self._current_path, self._previous_path)

        data = {k: v.to_dict() for k, v in schemas.items()}
        with open(self._current_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_current(self) -> dict[str, NodeSchema]:
        """Load current snapshot."""
        return self._load_from_path(self._current_path)

    def load_previous(self) -> dict[str, NodeSchema]:
        """Load previous snapshot."""
        return self._load_from_path(self._previous_path)

    def diff(
        self, old: dict[str, NodeSchema], new: dict[str, NodeSchema]
    ) -> dict[str, list[str]]:
        """Diff two snapshots. Returns {added: [...], removed: [...], changed: [...]}."""
        old_keys = set(old.keys())
        new_keys = set(new.keys())

        added = sorted(new_keys - old_keys)
        removed = sorted(old_keys - new_keys)
        changed = []
        for key in sorted(old_keys & new_keys):
            if old[key].to_dict() != new[key].to_dict():
                changed.append(key)

        return {"added": added, "removed": removed, "changed": changed}

    def _load_from_path(self, path: str) -> dict[str, NodeSchema]:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {k: NodeSchema.from_dict(v) for k, v in data.items()}
