"""M18 Tests — Multi-Step Decomposition + Workflow Chaining.

Тестирует:
- TaskDecomposer: decompose, split_by_conjunctions, analyze_part
- ExecutionChain: execute, cancel, retry per step
- Integration: chain execution с mock
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from app.engine.chain import ChainResult, ChainState, ExecutionChain, ChainStep
from app.engine.history import ExecutionHistory
from app.engine.job import Job, JobState
from app.planner.decomposer import SubTask, TaskDecomposer


# --- TaskDecomposer tests ---

class TestTaskDecomposer:
    def test_simple_request(self):
        decomposer = TaskDecomposer()
        result = decomposer.decompose("нарисуй кота")
        assert len(result) == 1
        assert result[0].capability == "image.generate"
        assert "кота" in result[0].params.get("prompt", "")

    def test_two_part_request(self):
        decomposer = TaskDecomposer()
        result = decomposer.decompose("нарисуй кота и увеличь разрешение")
        assert len(result) == 2
        assert result[0].capability == "image.generate"
        assert result[1].capability == "image.upscale"

    def test_three_part_request(self):
        decomposer = TaskDecomposer()
        result = decomposer.decompose("сгенерируй кота, потом улучши, затем увеличь")
        assert len(result) == 3
        assert result[0].capability == "image.generate"
        assert result[1].capability == "image.edit"
        assert result[2].capability == "image.upscale"

    def test_edit_request(self):
        decomposer = TaskDecomposer()
        result = decomposer.decompose("улучши качество изображения")
        assert len(result) == 1
        assert result[0].capability == "image.edit"

    def test_upscale_request(self):
        decomposer = TaskDecomposer()
        result = decomposer.decompose("увеличь разрешение до 1024x1024")
        assert len(result) == 1
        assert result[0].capability == "image.upscale"
        assert result[0].params.get("width") == 1024
        assert result[0].params.get("height") == 1024

    def test_complex_request(self):
        decomposer = TaskDecomposer()
        result = decomposer.decompose("нарисуй кота 512x512 и увеличь до 1024x1024")
        assert len(result) == 2
        assert result[0].capability == "image.generate"
        assert result[0].params.get("width") == 512
        assert result[1].capability == "image.upscale"
        assert result[1].params.get("width") == 1024

    def test_conjunction_and(self):
        decomposer = TaskDecomposer()
        result = decomposer.decompose("generate a cat and upscale it")
        assert len(result) == 2
        assert result[0].capability == "image.generate"
        assert result[1].capability == "image.upscale"

    def test_no_conjunction(self):
        decomposer = TaskDecomposer()
        result = decomposer.decompose("нарисуй красивого кота на фоне заката")
        assert len(result) == 1
        assert result[0].capability == "image.generate"


# --- ExecutionChain tests ---

class TestExecutionChain:
    def test_single_step_success(self):
        history = ExecutionHistory()
        mock_job = MagicMock()
        mock_job.prompt_id = "p1"
        mock_job.state.value = "SUCCESS"
        mock_job.workflow_id = "wf1"
        mock_job.version = "1.0"
        mock_job.output_assets = ["a1"]

        def execute_fn(subtask):
            return mock_job

        chain = ExecutionChain(execute_fn=execute_fn, history=history)
        result = chain.execute([SubTask(capability="image.generate", params={"prompt": "cat"})])

        assert result.ok is True
        assert result.completed_steps == 1
        assert result.failed_steps == 0

    def test_multi_step_success(self):
        history = ExecutionHistory()
        call_count = 0

        def execute_fn(subtask):
            nonlocal call_count
            call_count += 1
            job = MagicMock()
            job.prompt_id = f"p{call_count}"
            job.state.value = "SUCCESS"
            job.workflow_id = "wf1"
            job.version = "1.0"
            job.output_assets = [f"a{call_count}"]
            return job

        chain = ExecutionChain(execute_fn=execute_fn, history=history)
        result = chain.execute([
            SubTask(capability="image.generate", params={"prompt": "cat"}),
            SubTask(capability="image.upscale", params={"width": 1024}),
        ])

        assert result.ok is True
        assert result.completed_steps == 2

    def test_step_failure_stops_chain(self):
        history = ExecutionHistory()
        call_count = 0

        def execute_fn(subtask):
            nonlocal call_count
            call_count += 1
            job = MagicMock()
            job.prompt_id = f"p{call_count}"
            job.workflow_id = "wf1"
            job.version = "1.0"
            if call_count == 1:
                job.state.value = "FAILED"
                job.error = "error"
                job.output_assets = []
            else:
                job.state.value = "SUCCESS"
                job.output_assets = [f"a{call_count}"]
            return job

        # max_attempts_per_step=1 чтобы остановиться после первой неудачной попытки
        chain = ExecutionChain(execute_fn=execute_fn, history=history, max_attempts_per_step=1)
        result = chain.execute([
            SubTask(capability="image.generate", params={"prompt": "cat"}),
            SubTask(capability="image.upscale", params={"width": 1024}),
        ])

        assert result.ok is False
        assert result.completed_steps == 0
        assert result.failed_steps == 1

    def test_retry_on_failure(self):
        history = ExecutionHistory()
        attempt = 0

        def execute_fn(subtask):
            nonlocal attempt
            attempt += 1
            job = MagicMock()
            job.prompt_id = f"p{attempt}"
            job.workflow_id = "wf1"
            job.version = "1.0"
            if attempt < 3:
                job.state.value = "FAILED"
                job.error = "transient error"
                job.output_assets = []
            else:
                job.state.value = "SUCCESS"
                job.output_assets = ["a1"]
            return job

        chain = ExecutionChain(execute_fn=execute_fn, history=history, max_attempts_per_step=3)
        result = chain.execute([SubTask(capability="image.generate", params={"prompt": "cat"})])

        assert result.ok is True
        assert attempt == 3

    def test_cancel_chain(self):
        history = ExecutionHistory()
        call_count = 0

        def execute_fn(subtask):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Отменяем после первого шага
                chain.cancel()
            job = MagicMock()
            job.prompt_id = f"p{call_count}"
            job.state.value = "SUCCESS"
            job.workflow_id = "wf1"
            job.version = "1.0"
            job.output_assets = [f"a{call_count}"]
            return job

        chain = ExecutionChain(execute_fn=execute_fn, history=history)
        result = chain.execute([
            SubTask(capability="image.generate", params={"prompt": "cat"}),
            SubTask(capability="image.upscale", params={"width": 1024}),
            SubTask(capability="image.edit", params={"prompt": "enhance"}),
        ])

        assert result.state == ChainState.CANCELLED

    def test_chain_result_properties(self):
        result = ChainResult(
            state=ChainState.COMPLETED,
            steps=[],
            completed_steps=2,
            failed_steps=0,
        )
        assert result.ok is True

    def test_chain_step_is_terminal(self):
        step_running = ChainStep(subtask=SubTask(capability="image.generate"), state=ChainState.RUNNING)
        assert step_running.is_terminal is False

        step_completed = ChainStep(subtask=SubTask(capability="image.generate"), state=ChainState.COMPLETED)
        assert step_completed.is_terminal is True

        step_failed = ChainStep(subtask=SubTask(capability="image.generate"), state=ChainState.FAILED)
        assert step_failed.is_terminal is True

        step_cancelled = ChainStep(subtask=SubTask(capability="image.generate"), state=ChainState.CANCELLED)
        assert step_cancelled.is_terminal is True

    def test_on_step_complete_callback(self):
        history = ExecutionHistory()
        completed_steps = []

        def on_complete(index, step):
            completed_steps.append(index)

        def execute_fn(subtask):
            job = MagicMock()
            job.prompt_id = "p1"
            job.state.value = "SUCCESS"
            job.workflow_id = "wf1"
            job.version = "1.0"
            job.output_assets = ["a1"]
            return job

        chain = ExecutionChain(
            execute_fn=execute_fn,
            history=history,
            on_step_complete=on_complete,
        )
        result = chain.execute([
            SubTask(capability="image.generate", params={"prompt": "cat"}),
            SubTask(capability="image.upscale", params={"width": 1024}),
        ])

        assert completed_steps == [0, 1]
        assert result.completed_steps == 2

    def test_empty_chain(self):
        history = ExecutionHistory()

        def execute_fn(subtask):
            return MagicMock()

        chain = ExecutionChain(execute_fn=execute_fn, history=history)
        result = chain.execute([])

        assert result.ok is True
        assert result.completed_steps == 0


# --- Integration: ConversationAgent chain wiring ---

class TestConversationAgentChain:
    """Integration: ConversationAgent.turn() multi-step detection and chain execution."""

    def _make_mock_manifest(self, capability="image.generate"):
        """Создать mock manifest для тестов."""
        m = MagicMock()
        m.id = f"wf_{capability.replace('.', '_')}"
        m.version = "1.0"
        m.capability = capability
        # Mock asset_inputs: {role: mock_ain}
        input_ain = MagicMock()
        input_ain.kind = "image"
        m.asset_inputs = {"image": input_ain}
        return m

    def _make_mock_plan(self, capability="image.generate"):
        """Создать mock plan для тестов."""
        p = MagicMock()
        p.capability = capability
        p.params = {}
        p.asset_bindings = {}
        return p

    def test_single_step_regression(self, tmp_path):
        """Обычный single-step запрос идёт по существующему path (backward compat)."""
        from app.assets.store import AssetStore
        from app.conversation import ConversationAgent

        store = AssetStore(root=tmp_path)
        agent = ConversationAgent(store)

        # Decomposer вернёт 1 subtask → single-step path
        # (turn() вызовет существующий planner → prepare → execute)
        # Т.к. нет ComfyUI — ожидаем AgentError
        with pytest.raises(Exception):  # AgentError или similar
            agent.turn("s1", request="нарисуй кота")

    def test_multi_step_detection(self, tmp_path):
        """Multi-step request детектится через TaskDecomposer и возвращает failed Job."""
        from app.assets.store import AssetStore
        from app.conversation import ConversationAgent

        store = AssetStore(root=tmp_path)
        agent = ConversationAgent(store)

        # Decomposer вернёт 2 subtasks → chain path
        # Т.к. нет ComfyUI — chain вернёт failed Job (не exception)
        job = agent.turn("s1", request="нарисуй кота и увеличь разрешение")
        assert job.state == JobState.FAILED

    def test_chain_step_index_in_history(self, tmp_path):
        """Каждый шаг chain записывается в ExecutionHistory с chain_step_index."""
        from app.assets.store import AssetStore
        from app.conversation import ConversationAgent
        from app.engine.history import ExecutionHistory

        store = AssetStore(root=tmp_path)
        history = ExecutionHistory()
        agent = ConversationAgent(store, execution_history=history)

        call_count = 0

        def mock_execute(manifest, plan, **kwargs):
            nonlocal call_count
            call_count += 1
            job = Job(
                prompt_id=f"p{call_count}",
                workflow_id=manifest.id,
                version=manifest.version,
                capability=plan.capability,
                state=JobState.SUCCESS,
                output_assets=[f"a{call_count}"],
            )
            return job

        # Mock prepare() и engine.execute()
        def mock_prepare(cap, params=None, **kw):
            m = self._make_mock_manifest(cap)
            p = self._make_mock_plan(cap)
            return m, p, MagicMock()
        agent.prepare = mock_prepare
        agent.engine.execute = mock_execute

        from app.planner.decomposer import SubTask
        subtasks = [
            SubTask(capability="image.generate", params={"prompt": "cat"}),
            SubTask(capability="image.upscale", params={"width": 1024}),
        ]
        job = agent._execute_chain("s1", subtasks)

        # Проверяем history
        records = history.get_attempts()
        assert len(records) == 2
        assert records[0].chain_step_index == 0
        assert records[1].chain_step_index == 1
        assert records[0].capability == "image.generate"
        assert records[1].capability == "image.upscale"

    def test_chain_updates_session_context(self, tmp_path):
        """Chain обновляет ConversationContext после успешного выполнения."""
        from app.assets.store import AssetStore
        from app.conversation import ConversationAgent
        from app.engine.history import ExecutionHistory

        store = AssetStore(root=tmp_path)
        history = ExecutionHistory()
        agent = ConversationAgent(store, execution_history=history)

        call_count = 0

        def mock_execute(manifest, plan, **kwargs):
            nonlocal call_count
            call_count += 1
            job = Job(
                prompt_id=f"p{call_count}",
                workflow_id=manifest.id,
                version=manifest.version,
                capability=plan.capability,
                state=JobState.SUCCESS,
                output_assets=[f"a{call_count}"],
            )
            return job

        def mock_prepare(cap, params=None, **kw):
            m = self._make_mock_manifest(cap)
            p = self._make_mock_plan(cap)
            return m, p, MagicMock()
        agent.prepare = mock_prepare
        agent.engine.execute = mock_execute

        from app.planner.decomposer import SubTask
        subtasks = [
            SubTask(capability="image.generate", params={"prompt": "cat"}),
            SubTask(capability="image.upscale", params={"width": 1024}),
        ]
        job = agent._execute_chain("s1", subtasks)

        ctx = agent.context("s1")
        assert ctx.active_asset == "a2"  # последний output
        assert "a1" in ctx.assets
        assert "a2" in ctx.assets
        assert ctx.dialog_state == "idle"

    def test_session_isolation_chain(self, tmp_path):
        """Chain в разных sessions не влияют друг на друга."""
        from app.assets.store import AssetStore
        from app.conversation import ConversationAgent
        from app.engine.history import ExecutionHistory

        store = AssetStore(root=tmp_path)
        history = ExecutionHistory()
        agent = ConversationAgent(store, execution_history=history)

        call_count = 0

        def mock_execute(manifest, plan, **kwargs):
            nonlocal call_count
            call_count += 1
            job = Job(
                prompt_id=f"p{call_count}",
                workflow_id=manifest.id,
                version=manifest.version,
                capability=plan.capability,
                state=JobState.SUCCESS,
                output_assets=[f"a{call_count}"],
            )
            return job

        def mock_prepare(cap, params=None, **kw):
            m = self._make_mock_manifest(cap)
            p = self._make_mock_plan(cap)
            return m, p, MagicMock()
        agent.prepare = mock_prepare
        agent.engine.execute = mock_execute

        from app.planner.decomposer import SubTask

        # Session A
        agent._execute_chain("A", [
            SubTask(capability="image.generate", params={"prompt": "cat"}),
        ])
        # Session B
        agent._execute_chain("B", [
            SubTask(capability="image.generate", params={"prompt": "dog"}),
        ])

        ctx_a = agent.context("A")
        ctx_b = agent.context("B")
        assert ctx_a.active_asset != ctx_b.active_asset
        assert "a1" in ctx_a.assets
        assert "a2" in ctx_b.assets
