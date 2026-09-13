#!/usr/bin/env python3
"""
Генератор справочника нод ComfyUI.

Создаёт docs/COMFYUI_NODE_REFERENCE.md из /object_info + NodeDocStore.
Запуск: python scripts/generate_node_reference.py [--output path]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.comfy.client import ComfyClient  # noqa: E402
from app.knowledge.node_doc import NodeDocStore  # noqa: E402


def generate_reference(
    object_info: dict,
    node_doc_store: NodeDocStore,
    output_path: str,
) -> None:
    """Генерирует markdown справочник."""

    lines = [
        "# ComfyUI Node Reference",
        "",
        f"> Auto-generated from /object_info | Nodes: {len(object_info)}",
        f"> Documented nodes: {node_doc_store.count()}",
        "",
        "---",
        "",
        "## Table of Contents",
        "",
        "- [By Category](#by-category)",
        "- [All Nodes](#all-nodes)",
        "",
        "---",
        "",
        "## By Category",
        "",
    ]

    # Группируем по категориям
    categories: dict[str, list[str]] = {}
    for node_class, node_data in object_info.items():
        if isinstance(node_data, dict) and "category" in node_data:
            cat = node_data["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(node_class)

    for cat in sorted(categories.keys()):
        nodes = sorted(categories[cat])
        lines.append(f"### {cat}")
        for node in nodes:
            doc = node_doc_store.get_doc_for(node)
            doc_marker = " ✓" if doc else ""
            anchor = node.lower().replace(" ", "-")
            lines.append(f"- [{node}](#{anchor}){doc_marker}")
        lines.append("")

    lines.extend(["---", "", "## All Nodes", ""])

    # Все ноды
    for node_class in sorted(object_info.keys()):
        node_data = object_info[node_class]
        if not isinstance(node_data, dict):
            continue

        doc = node_doc_store.get_doc_for(node_class)

        lines.extend([
            f"### {node_class}",
            "",
            f"- **Category:** {node_data.get('category', 'Unknown')}",
            f"- **Documented:** {'Yes' if doc else 'No'}",
            "",
        ])

        if doc:
            lines.append(f"**Purpose:** {doc.purpose}")
            lines.append("")

            # Inputs (required)
            required = node_data.get("input", {}).get("required", {})
            if required:
                lines.append("**Required Inputs:**")
                lines.append("| Name | Type | Default | Description |")
                lines.append("|------|------|---------|-------------|")
                for input_name, input_data in required.items():
                    if isinstance(input_data, list) and len(input_data) >= 1:
                        input_type = str(input_data[0])
                    else:
                        input_type = str(input_data)
                    default = ""
                    if isinstance(input_data, list) and len(input_data) >= 2:
                        meta = input_data[1]
                        if isinstance(meta, dict):
                            default = meta.get("default", "")
                    desc = ""
                    if doc and input_name in doc.inputs_documented:
                        info = doc.inputs_documented[input_name]
                        if isinstance(info, dict):
                            desc = info.get("description", "")
                    lines.append(f"| {input_name} | {input_type} | {default} | {desc} |")
                lines.append("")

            # Outputs
            outputs = node_data.get("output", [])
            output_names = node_data.get("output_name", [])
            if outputs:
                lines.append("**Outputs:**")
                for i, output_type in enumerate(outputs):
                    name = output_names[i] if i < len(output_names) else f"output_{i}"
                    desc = ""
                    if doc and name in doc.outputs_documented:
                        info = doc.outputs_documented[name]
                        if isinstance(info, dict):
                            desc = info.get("description", "")
                    lines.append(f"- `{name}` ({output_type}): {desc}")
                lines.append("")

            # Configuration
            if doc and doc.configuration:
                lines.append("**Configuration:**")
                for key, value in doc.configuration.items():
                    lines.append(f"- {key}: {value}")
                lines.append("")

            # Related
            if doc and doc.related_nodes:
                lines.append(f"**Related:** {', '.join(doc.related_nodes)}")
                lines.append("")

        lines.append("---")
        lines.append("")

    # Записываем
    os = __import__("os")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Generated reference: {output_path}")
    print(f"Total nodes: {len(object_info)}")
    print(f"Documented: {node_doc_store.count()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Генератор справочника нод ComfyUI")
    parser.add_argument(
        "--output",
        default="docs/COMFYUI_NODE_REFERENCE.md",
        help="Путь к выходному файлу",
    )
    args = parser.parse_args()

    # Загружаем /object_info
    client = ComfyClient()
    print("Fetching /object_info...")
    object_info = client.get_object_info()

    # Загружаем документацию
    node_doc_store = NodeDocStore()
    print(f"Loaded {node_doc_store.count()} documented nodes")

    # Генерируем
    generate_reference(object_info, node_doc_store, args.output)


if __name__ == "__main__":
    main()
