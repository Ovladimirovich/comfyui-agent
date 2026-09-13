"""LocalResearchProvider — исследование локальных источников для semantic evidence.

Читает:
  - README*.md в каталоге custom node
  - Python source: NODE_CLASS_MAPPINGS, INPUT_TYPES, RETURN_TYPES, RETURN_NAMES, FUNCTION
  - package metadata (pyproject.toml, setup.py)

НЕ читает: web, LLM, remote API.
НЕ модифицирует ClaimStatus напрямую — только выдаёт ResearchResult.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Optional

from app.knowledge.models import EvidenceSource, EvidenceTrustLevel, KnowledgeEvidence
from app.knowledge.research import ResearchResult


@dataclass(frozen=True)
class ResearchSource:
    """Один локальный источник."""

    path: str
    kind: str  # "readme" | "python_source" | "metadata"
    content_preview: str = ""


class LocalResearchProvider:
    """Исследует локальные источники (README, source code, metadata)."""

    def __init__(self, custom_nodes_dir: Optional[str] = None) -> None:
        if custom_nodes_dir is None:
            custom_nodes_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "ComfyUI", "custom_nodes",
            )
        self._custom_nodes_dir = custom_nodes_dir

    # --- public API -------------------------------------------------------

    def research(self, request) -> ResearchResult:
        """Исследовать источники для claim из ResearchRequest.

        Возвращает ResearchResult с найденными evidence.
        """
        claim = request.claim
        subject = claim.subject
        preferred = list(request.preferred_sources)

        evidence_list = []
        sources_checked: list[str] = []
        unresolved: list[str] = []

        # 1. README
        readme_evidence, readme_checked, readme_unresolved = self._research_readme(subject)
        evidence_list.extend(readme_evidence)
        sources_checked.extend(readme_checked)
        unresolved.extend(readme_unresolved)

        # 2. Python source
        source_evidence, source_checked, source_unresolved = self._research_source(subject)
        evidence_list.extend(source_evidence)
        sources_checked.extend(source_checked)
        unresolved.extend(source_unresolved)

        # 3. Metadata
        meta_evidence, meta_checked, meta_unresolved = self._research_metadata(subject)
        evidence_list.extend(meta_evidence)
        sources_checked.extend(meta_checked)
        unresolved.extend(meta_unresolved)

        return ResearchResult(
            evidence=tuple(evidence_list),
            unresolved=tuple(unresolved),
            sources_checked=tuple(sources_checked),
        )

    def list_sources(self, subject: str) -> list[ResearchSource]:
        """Перечислить все доступные локальные источники для node/class."""
        sources: list[ResearchSource] = []
        sources.extend(self._find_readmes(subject))
        sources.extend(self._find_python_sources(subject))
        sources.extend(self._find_metadata_files(subject))
        return sources

    # --- Private: README --------------------------------------------------

    def _research_readme(self, subject: str) -> tuple[list, list, list]:
        """Исследовать README*.md файлы для указаннаяго subject."""
        evidence: list = []
        checked: list = []
        unresolved: list = []

        node_dir = self._find_node_dir(subject)
        if node_dir is None:
            unresolved.append(f"node dir not found for {subject}")
            return evidence, checked, unresolved

        readmes = self._find_readmes_in_dir(node_dir)
        for readme_path in readmes:
            checked.append(f"local:{readme_path}")
            try:
                content = self._read_file(readme_path)
                preview = content[:200].replace("\n", " ")
                evidence.append(KnowledgeEvidence(
                    source=f"local:{readme_path}",
                    source_type=EvidenceSource.LOCAL_SOURCE,
                    trust_level=EvidenceTrustLevel.DECLARED_PURPOSE,
                    timestamp=time.time(),
                    claim=f"README declares purpose of {subject}: {preview}",
                ))

                # Semantic extraction from README
                semantics = self._extract_semantics_from_readme(content, subject)
                for sem in semantics:
                    evidence.append(KnowledgeEvidence(
                        source=f"local:{readme_path}",
                        source_type=EvidenceSource.LOCAL_SOURCE,
                        trust_level=EvidenceTrustLevel.DECLARED_PURPOSE,
                        timestamp=time.time(),
                        claim=sem,
                    ))
            except Exception as e:
                unresolved.append(f"failed to read {readme_path}: {e}")

        return evidence, checked, unresolved

    def _extract_semantics_from_readme(self, content: str, subject: str) -> list[str]:
        """Извлечь семантические утверждения из README."""
        semantics = []
        lines = content.split("\n")

        for line in lines:
            line_lower = line.lower().strip()
            # Mode descriptions
            if "image to video" in line_lower or "img2video" in line_lower:
                semantics.append(f"{subject}: declares image-to-video capability from README")
            if "text to video" in line_lower or "txt2video" in line_lower:
                semantics.append(f"{subject}: declares text-to-video capability from README")
            if "first and last" in line_lower or "keyframe" in line_lower:
                semantics.append(f"{subject}: declares first-last-frame / keyframe capability from README")
            if "video" in line_lower and ("output" in line_lower or "produce" in line_lower or "generate" in line_lower):
                semantics.append(f"{subject}: declares video output from README")
            if "prompt" in line_lower and "input" in line_lower:
                semantics.append(f"{subject}: declares prompt input from README")

        return semantics

    # --- Private: Python source -------------------------------------------

    def _research_source(self, subject: str) -> tuple[list, list, list]:
        """Исследовать Python source файлы для указанноого node."""
        evidence: list = []
        checked: list = []
        unresolved: list = []

        node_dir = self._find_node_dir(subject)
        if node_dir is None:
            unresolved.append(f"node dir not found for {subject}")
            return evidence, checked, unresolved

        py_files = self._find_python_files(node_dir)
        for py_path in py_files:
            checked.append(f"local:{py_path}")
            try:
                content = self._read_file(py_path)
                preview = content[:200].replace("\n", " ")
                evidence.append(KnowledgeEvidence(
                    source=f"local:{py_path}",
                    source_type=EvidenceSource.LOCAL_SOURCE,
                    trust_level=EvidenceTrustLevel.OBSERVED_SOURCE_STRUCTURE,
                    timestamp=time.time(),
                    claim=f"Source structure of {subject} in {os.path.basename(py_path)}: {preview}",
                ))

                # Extract structured info
                struct_info = self._extract_source_structure(content, subject, py_path)
                for info in struct_info:
                    evidence.append(KnowledgeEvidence(
                        source=f"local:{py_path}",
                        source_type=EvidenceSource.LOCAL_SOURCE,
                        trust_level=EvidenceTrustLevel.OBSERVED_SOURCE_STRUCTURE,
                        timestamp=time.time(),
                        claim=info,
                    ))
            except Exception as e:
                unresolved.append(f"failed to parse {py_path}: {e}")

        return evidence, checked, unresolved

    def _extract_source_structure(self, content: str, subject: str, path: str) -> list[str]:
        """Извлечь структурированную информацию из Python source."""
        info = []

        # NODE_CLASS_MAPPINGS
        pattern = r"NODE_CLASS_MAPPINGS\s*=\s*\{([^}]+)\}"
        match = re.search(pattern, content)
        if match:
            mappings = match.group(1)
            if subject in mappings:
                info.append(f"{subject}: present in NODE_CLASS_MAPPINGS (observed from source)")

        # INPUT_TYPES
        pattern = r"def INPUT_TYPES\(cls\):[\s\S]*?return\s*\{([^}]+)\}"
        match = re.search(pattern, content)
        if match:
            inputs = match.group(1)
            if "mode" in inputs and "Image To Video" in inputs:
                info.append(f"{subject}: INPUT_TYPES declares 'Image To Video' mode (observed from source)")
            if "end_frame" in inputs:
                info.append(f"{subject}: INPUT_TYPES declares 'end_frame' input (observed from source)")
            if "prompt" in inputs:
                info.append(f"{subject}: INPUT_TYPES declares 'prompt' input (observed from source)")

        # RETURN_TYPES
        pattern = r"RETURN_TYPES\s*=\s*\((.+?)\)"
        match = re.search(pattern, content)
        if match:
            types_str = match.group(1)
            if "VIDEO" in types_str or "_VIDEO_TYPE" in types_str:
                info.append(f"{subject}: RETURN_TYPES includes VIDEO output (observed from source)")
            if '"IMAGE"' in types_str or "'IMAGE'" in types_str:
                info.append(f"{subject}: RETURN_TYPES includes IMAGE output (observed from source)")
            if '"AUDIO"' in types_str or "'AUDIO'" in types_str:
                info.append(f"{subject}: RETURN_TYPES includes AUDIO output (observed from source)")

        # FUNCTION
        if "FUNCTION = " in content:
            func_match = re.search(r"FUNCTION\s*=\s*['\"](\w+)['\"]", content)
            if func_match:
                info.append(f"{subject}: execution function is '{func_match.group(1)}' (observed from source)")

        return info

    # --- Private: Metadata ------------------------------------------------

    def _research_metadata(self, subject: str) -> tuple[list, list, list]:
        """Исследовать package metadata."""
        evidence: list = []
        checked: list = []
        unresolved: list = []

        node_dir = self._find_node_dir(subject)
        if node_dir is None:
            return evidence, checked, unresolved

        meta_files = self._find_metadata_files(node_dir)
        for meta_path in meta_files:
            checked.append(f"local:{meta_path}")
            try:
                content = self._read_file(meta_path)
                preview = content[:200].replace("\n", " ")
                evidence.append(KnowledgeEvidence(
                    source=f"local:{meta_path}",
                    source_type=EvidenceSource.PROJECT_METADATA,
                    trust_level=EvidenceTrustLevel.DECLARED_PURPOSE,
                    timestamp=time.time(),
                    claim=f"Metadata for {subject} package: {preview}",
                ))
            except Exception as e:
                unresolved.append(f"failed to read {meta_path}: {e}")

        return evidence, checked, unresolved

    # --- Private: file discovery ------------------------------------------

    def _find_node_dir(self, subject: str) -> Optional[str]:
        """Найти каталог custom node по имени класса или категории."""
        if not os.path.isdir(self._custom_nodes_dir):
            return None

        for entry in os.listdir(self._custom_nodes_dir):
            dir_path = os.path.join(self._custom_nodes_dir, entry)
            if not os.path.isdir(dir_path):
                continue

            # Check if subject appears in any Python file
            for py_file in self._find_python_files(dir_path):
                try:
                    content = self._read_file(py_file)
                    if subject in content:
                        return dir_path
                except Exception:
                    pass

            # Also check README
            for rm in self._find_readmes_in_dir(dir_path):
                try:
                    content = self._read_file(rm)
                    if subject in content:
                        return dir_path
                except Exception:
                    pass

        return None

    def _find_readmes(self, subject: str) -> list[ResearchSource]:
        """Найти README файлы для указанного subject."""
        sources = []
        node_dir = self._find_node_dir(subject)
        if node_dir:
            for rm_path in self._find_readmes_in_dir(node_dir):
                try:
                    content = self._read_file(rm_path)
                    sources.append(ResearchSource(
                        path=rm_path,
                        kind="readme",
                        content_preview=content[:200].replace("\n", " "),
                    ))
                except Exception:
                    pass
        return sources

    def _find_python_sources(self, subject: str) -> list[ResearchSource]:
        """Найти Python source файлы для указанного subject."""
        sources = []
        node_dir = self._find_node_dir(subject)
        if node_dir:
            for py_path in self._find_python_files(node_dir):
                try:
                    content = self._read_file(py_path)
                    sources.append(ResearchSource(
                        path=py_path,
                        kind="python_source",
                        content_preview=content[:200].replace("\n", " "),
                    ))
                except Exception:
                    pass
        return sources

    def _find_readmes_in_dir(self, dir_path: str) -> list[str]:
        """Найти все README*.md файлы в каталоге."""
        results = []
        for entry in sorted(os.listdir(dir_path)):
            if entry.startswith("README") and entry.endswith((".md", ".MD")):
                results.append(os.path.join(dir_path, entry))
        return results

    def _find_python_files(self, dir_path: str) -> list[str]:
        """Найти все .py файлы в каталоге (не __init__, не __pycache__)."""
        results = []
        if not os.path.isdir(dir_path):
            return results
        for entry in sorted(os.listdir(dir_path)):
            if entry.endswith(".py") and entry != "__init__.py":
                full = os.path.join(dir_path, entry)
                if os.path.isfile(full):
                    results.append(full)
        return results

    def _find_metadata_files(self, dir_path: str) -> list[str]:
        """Найти package metadata файлы."""
        results = []
        if not os.path.isdir(dir_path):
            return results
        for name in ("pyproject.toml", "setup.py", "setup.cfg", "package.json"):
            full = os.path.join(dir_path, name)
            if os.path.isfile(full):
                results.append(full)
        return results

    # --- Private: helpers -------------------------------------------------

    @staticmethod
    def _read_file(path: str) -> str:
        """Прочитать файл с fallback encoding."""
        for enc in ("utf-8", "latin-1", "cp1251"):
            try:
                with open(path, "r", encoding=enc) as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
