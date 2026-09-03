"""Capability Graph — граф composability capabilities.

AD-41: Строится из CapabilityRegistry. Edges определяются media type compatibility.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.registry.capability import Capability, CapabilityRegistry


class CapabilityGraph:
    """Граф composability capabilities.
    
    Nodes: Capabilities
    Edges: Composability (output_A ∈ input_B)
    """
    
    def __init__(self, registry: CapabilityRegistry) -> None:
        self._registry = registry
        self._graph: dict[str, set[str]] = defaultdict(set)
        self._build_graph()
    
    def _build_graph(self) -> None:
        """Построить граф из зарегистрированных capabilities."""
        capabilities = self._registry.all()
        
        for cap in capabilities:
            if cap.media_output is None:
                continue
            
            for other in capabilities:
                if cap.id == other.id:
                    continue
                
                # Проверяем composability: output_A ∈ input_B
                if cap.media_output in other.media_input:
                    self._graph[cap.id].add(other.id)
    
    def get_composability(self, from_cap: str, to_cap: str) -> bool:
        """Проверить composability двух capabilities."""
        return to_cap in self._graph.get(from_cap, set())
    
    def get_successors(self, capability_id: str) -> set[str]:
        """Получить все capabilities, совместимые с данным."""
        return self._graph.get(capability_id, set())
    
    def find_paths(
        self,
        target: str,
        available_types: set[str] | None = None,
        max_length: int = 5,
    ) -> list[list[str]]:
        """Найти все composable paths к target capability.
        
        Args:
            target: Целевая capability
            available_types: Доступные типы media на входе
            max_length: Максимальная длина chain
            
        Returns:
            Список paths (каждый path — список capability IDs)
        """
        if available_types is None:
            available_types = set()
        
        # Начальные capabilities: те, которые не требуют входных данных
        # или требуют данные из available_types
        start_caps = []
        for cap in self._registry.all():
            if not cap.media_input or cap.media_input == () or cap.media_input[0] in available_types:
                start_caps.append(cap.id)
        
        paths: list[list[str]] = []
        
        # BFS для поиска всех paths
        queue: deque[tuple[str, list[str]]] = deque()
        for start in start_caps:
            queue.append((start, [start]))
        
        while queue:
            current, path = queue.popleft()
            
            if current == target:
                paths.append(path)
                continue
            
            if len(path) >= max_length:
                continue
            
            for successor in self._graph.get(current, set()):
                if successor not in path:  # Избегаем циклов
                    queue.append((successor, path + [successor]))
        
        return paths
    
    def get_all_capabilities(self) -> list[str]:
        """Получить все capability IDs в графе."""
        return [cap.id for cap in self._registry.all()]
