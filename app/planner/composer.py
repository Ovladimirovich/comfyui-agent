"""Composer — сборка capability chain из пользовательского intent.

AD-41: Отдельный класс, НЕ часть Planner протокола.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from app.planner.capability_graph import CapabilityGraph
from app.planner.composition_result import CompositionResult

if TYPE_CHECKING:
    from app.engine.chain import SubTask
    from app.engine.semantic_verifier import SemanticVerifier
    from app.registry.capability import CapabilityRegistry
    from app.registry.registry import WorkflowRegistry

MAX_CHAIN_LENGTH = 5
MAX_ALTERNATIVES = 3


class Composer:
    """Собирает chain из capabilities для достижения target capability.
    
    AD-41 Decisions:
    - Composer — отдельный класс, НЕ часть Planner протокола
    - Parameter mapping: identity mapping (params pass-through)
    - Intermediate verification: optional, default off
    - Max chain length: 5 steps
    - Alternative paths: up to 3 variants
    """
    
    def __init__(
        self,
        capability_registry: CapabilityRegistry,
        workflow_registry: WorkflowRegistry,
        semantic_verifier: SemanticVerifier | None = None,
        max_chain_length: int = MAX_CHAIN_LENGTH,
    ) -> None:
        self._cap_registry = capability_registry
        self._wf_registry = workflow_registry
        self._verifier = semantic_verifier
        self._max_chain_length = max_chain_length
        self._graph = CapabilityGraph(capability_registry)
    
    def compose(
        self,
        target_capability: str,
        params: dict,
        available_types: set[str] | None = None,
    ) -> CompositionResult:
        """Составить chain для достижения target capability.
        
        Args:
            target_capability: Целевая capability (например, "image.upscale")
            params: Параметры для каждого шага
            available_types: Доступные типы media на входе
            
        Returns:
            CompositionResult с chain или failure reason
        """
        if available_types is None:
            available_types = set()
        
        # Проверяем существование target capability
        target = self._cap_registry.get(target_capability)
        if target is None:
            return CompositionResult.fail(
                f"Capability '{target_capability}' not found",
                suggestions=["Check available capabilities"],
            )
        
        # Ищем все paths к target
        paths = self._graph.find_paths(
            target=target_capability,
            available_types=available_types,
            max_length=self._max_chain_length,
        )
        
        if not paths:
            return CompositionResult.fail(
                f"No composable path to '{target_capability}'",
                suggestions=self._get_alternative_suggestions(target_capability),
            )
        
        # Выбираем лучший path (самый короткий)
        best_path = min(paths, key=len)
        
        # Создаём alternatives (до MAX_ALTERNATIVES)
        alternatives = []
        for path in paths:
            if path != best_path and len(alternatives) < MAX_ALTERNATIVES:
                alternatives.append(path)
        
        # Конвертируем path в SubTasks
        chain = self._path_to_subtasks(best_path, params)
        alt_chains = [self._path_to_subtasks(p, params) for p in alternatives]
        
        return CompositionResult.ok(chain=chain, alternatives=alt_chains)
    
    def _path_to_subtasks(self, path: list[str], params: dict) -> list[SubTask]:
        """Конвертировать path (list of capability IDs) в SubTasks."""
        from app.engine.chain import SubTask
        
        subtasks: list[SubTask] = []
        for cap_id in path:
            cap = self._cap_registry.get(cap_id)
            if cap is None:
                continue
            
            # Identity mapping: передаём params как есть
            step_params = dict(params)
            
            # Добавляем capability-specific defaults
            if cap.default_workflow:
                step_params.setdefault("workflow", cap.default_workflow)
            
            subtasks.append(SubTask(
                capability=cap_id,
                params=step_params,
            ))
        
        return subtasks
    
    def _get_alternative_suggestions(self, target: str) -> list[str]:
        """Получить альтернативные предложения для недоступной capability."""
        suggestions = []
        
        # Предлагаем capabilities с похожим media_output
        target_cap = self._cap_registry.get(target)
        if target_cap and target_cap.media_output:
            for cap in self._cap_registry.all():
                if cap.media_output == target_cap.media_output and cap.id != target:
                    suggestions.append(f"Try '{cap.id}' instead")
        
        return suggestions[:3]