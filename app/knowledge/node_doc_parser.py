"""
NodeDocParser — парсер markdown документации нод ComfyUI.

Поддерживаемый формат:

## NodeName
- **Category:** RequestNode/Get Request
- **Purpose:** HTTP GET запрос
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Post Request Node, Rest Api Node

**Inputs:**
- `target_url` (STRING, required): URL для запроса
- `headers` (KEY_VALUE, optional): Заголовки HTTP

**Outputs:**
- `text` (STRING): Ответ как текст
- `json` (JSON): Ответ как JSON

**Configuration:**
- proxy: Не используется
- timeout: System default

**Example:**
```json
{"target_url": "https://api.example.com"}
```
"""

from __future__ import annotations

import json
import re
from typing import Optional

from .node_doc import NodeDocEntry


class NodeDocParser:
    """Парсер markdown документации нод."""

    def parse_file(self, path: str) -> list[NodeDocEntry]:
        """Парсит markdown файл."""
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        return self.parse_text(text, source_file=path)

    def parse_text(self, text: str, source_file: str = "") -> list[NodeDocEntry]:
        """Парсит текст, возвращает список NodeDocEntry."""
        entries: list[NodeDocEntry] = []

        # Разбиваем на секции по ## (но не ###)
        # Поддерживаем начало строки или \n перед ##
        sections = re.split(r"(?:^|\n)## (?=[A-Z])", text)

        for section in sections:
            if not section.strip():
                continue
            entry = self._parse_section(section, source_file)
            if entry:
                entries.append(entry)

        return entries

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _parse_section(self, section: str, source_file: str) -> Optional[NodeDocEntry]:
        """Парсит одну секцию (ноду)."""
        lines = section.strip().split("\n")
        if not lines:
            return None

        # Имя ноды — первая строка (заголовок)
        node_class = lines[0].strip().lstrip("#").strip()
        if not node_class:
            return None

        # Инициализация
        category = ""
        purpose = ""
        python_module = ""
        related_nodes: list[str] = []
        inputs_documented: dict = {}
        outputs_documented: dict = {}
        configuration: dict = {}
        examples: list[dict] = []

        current_section: Optional[str] = None
        in_code_block = False

        for raw_line in lines[1:]:
            line = raw_line.strip()

            # Пропускаем code blocks (не парсим содержимое)
            if line.startswith("```"):
                in_code_block = not in_code_block
                if in_code_block and current_section == "example":
                    # Начало JSON блока — следующая строка будет JSON
                    pass
                elif not in_code_block and current_section == "example":
                    # Конец JSON блока
                    pass
                continue

            if in_code_block:
                # Внутри JSON блока — парсим как пример
                if current_section == "example":
                    try:
                        workflow = json.loads(line)
                        examples.append({"name": "Example", "workflow": workflow})
                    except json.JSONDecodeError:
                        pass
                continue

            if not line:
                current_section = None
                continue

            # Метаданные (строки вида "- **Key:** value")
            if line.startswith("- **Category:**") or line.startswith("- **Категория:**"):
                category = self._extract_value(line)
                continue
            if line.startswith("- **Purpose:**") or line.startswith("- **Назначение:**"):
                purpose = self._extract_value(line)
                continue
            if line.startswith("- **Module:**") or line.startswith("- **Модуль:**"):
                python_module = self._extract_value(line)
                continue
            if line.startswith("- **Related:**") or line.startswith("- **Связанные:**"):
                related_text = self._extract_value(line)
                related_nodes = [r.strip() for r in related_text.split(",") if r.strip()]
                continue

            # Секции
            lower = line.lower()
            if "inputs" in lower or "входы" in lower:
                if line.startswith("**") and line.endswith("**"):
                    current_section = "inputs"
                    continue
            if "outputs" in lower or "выходы" in lower:
                if line.startswith("**") and line.endswith("**"):
                    current_section = "outputs"
                    continue
            if "configuration" in lower or "конфигурация" in lower:
                if line.startswith("**") and line.endswith("**"):
                    current_section = "config"
                    continue
            if "example" in lower or "пример" in lower:
                if line.startswith("**") and line.endswith("**"):
                    current_section = "example"
                    continue

            # Парсинг содержимого секций
            if current_section == "inputs":
                field = self._parse_field(line)
                if field:
                    inputs_documented[field["name"]] = field
            elif current_section == "outputs":
                field = self._parse_field(line)
                if field:
                    outputs_documented[field["name"]] = field
            elif current_section == "config":
                config = self._parse_config(line)
                if config:
                    configuration.update(config)

        if not node_class:
            return None

        return NodeDocEntry(
            node_class=node_class,
            display_name=node_class,
            category=category,
            purpose=purpose,
            python_module=python_module,
            inputs_documented=inputs_documented,
            outputs_documented=outputs_documented,
            configuration=configuration,
            examples=examples,
            related_nodes=related_nodes,
            source_file=source_file,
        )

    def _extract_value(self, line: str) -> str:
        """Извлекает значение из строки '- **Key:** value'."""
        # Формат: - **Key:** value (двоеточие внутри bold)
        match = re.search(r"\*\*[^*]+\*\*\s*(.+)", line)
        return match.group(1).strip() if match else ""

    def _parse_field(self, line: str) -> Optional[dict]:
        """Парсит строку: - `name` (TYPE, required/optional): description."""
        match = re.match(r"-\s*`([^`]+)`\s*\(([^)]+)\):\s*(.+)", line)
        if not match:
            return None

        name = match.group(1)
        type_info = match.group(2)
        description = match.group(3)

        parts = [p.strip().lower() for p in type_info.split(",")]
        field_type = parts[0].upper() if parts else "UNKNOWN"
        required = "required" in parts or "обязательный" in parts

        default = None
        default_match = re.search(r"default:\s*([^)]+)", type_info, re.IGNORECASE)
        if default_match:
            default = default_match.group(1).strip()

        options: list[str] = []
        opt_match = re.search(r"\[([^\]]+)\]", type_info)
        if opt_match:
            options = [o.strip() for o in opt_match.group(1).split(",")]

        result: dict = {
            "name": name,
            "type": field_type,
            "required": required,
            "description": description,
        }
        if default is not None:
            result["default"] = default
        if options:
            result["options"] = options

        return result

    def _parse_config(self, line: str) -> Optional[dict]:
        """Парсит строку: - key: value."""
        match = re.match(r"- ([^:]+):\s*(.+)", line)
        if match:
            return {match.group(1).strip(): match.group(2).strip()}
        return None


# ------------------------------------------------------------------
# Formatting helpers (used by CLI / MCP)
# ------------------------------------------------------------------


def format_node_explanation(doc: NodeDocEntry) -> str:
    """Форматирует объяснение ноды для вывода."""
    lines = [
        f"# {doc.node_class}",
        f"**Category:** {doc.category}",
        f"**Purpose:** {doc.purpose}",
        f"**Module:** {doc.python_module}",
        "",
    ]

    # Inputs
    if doc.inputs_documented:
        lines.append("## Inputs")
        lines.append("| Name | Type | Required | Default | Description |")
        lines.append("|------|------|----------|---------|-------------|")
        for name, info in doc.inputs_documented.items():
            if isinstance(info, dict):
                required = "Yes" if info.get("required") else "No"
                default = info.get("default", "-")
                if default is None:
                    default = "-"
                desc = info.get("description", "")
                lines.append(
                    f"| {name} | {info.get('type', '?')} | {required} | {default} | {desc} |"
                )
        lines.append("")

    # Outputs
    if doc.outputs_documented:
        lines.append("## Outputs")
        lines.append("| Name | Type | Description |")
        lines.append("|------|------|-------------|")
        for name, info in doc.outputs_documented.items():
            if isinstance(info, dict):
                desc = info.get("description", "")
                lines.append(f"| {name} | {info.get('type', '?')} | {desc} |")
        lines.append("")

    # Configuration
    if doc.configuration:
        lines.append("## Configuration")
        for key, value in doc.configuration.items():
            lines.append(f"- **{key}:** {value}")
        lines.append("")

    # Related
    if doc.related_nodes:
        lines.append(f"**Related:** {', '.join(doc.related_nodes)}")

    return "\n".join(lines)
