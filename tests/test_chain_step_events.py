from unittest.mock import patch, MagicMock
from app.assets.store import AssetStore
from app.conversation import ConversationAgent
from app.engine.job import Job, JobState
from app.planner.decomposer import SubTask


# --- Unit test: turn() пробрасывает on_chain_step в _execute_chain ---

def test_turn_passes_on_chain_step_to_execute_chain(tmp_path):
    store = AssetStore(root=tmp_path)
    agent = ConversationAgent(store)
    events = []

    # Мокаем _execute_chain_step чтобы вернуть SUCCESS Job
    def _mock_execute_chain_step(subtask, **_kw):
        return Job(
            prompt_id="p1",
            workflow_id="txt2img",
            version="1.0.0",
            capability=subtask.capability,
            state=JobState.SUCCESS,
            output_assets=["asset1"],
        )

    # Мокаем _execute_chain чтобы он вызывал переданный on_chain_step
    def _mock_execute_chain(
        self, session_id, subtasks, on_chain_step=None, **_kw
    ):
        for i, subtask in enumerate(subtasks):
            if on_chain_step:
                on_chain_step({
                    "type": "chain_step",
                    "step": i,
                    "total_steps": len(subtasks),
                    "state": "completed",
                    "capability": subtask.capability,
                    "outputs": ["asset1"],
                })
        return Job(
            prompt_id="p1",
            workflow_id="txt2img",
            version="1.0.0",
            capability=subtasks[-1].capability,
            state=JobState.SUCCESS,
            output_assets=["asset1"],
        )

    # Заменяем _execute_chain_step и _execute_chain
    with patch.object(agent, "_execute_chain_step", side_effect=_mock_execute_chain_step):
        with patch.object(agent, "_execute_chain", side_effect=_mock_execute_chain):
            # Вызываем turn с on_chain_step=collector
            def _collector(ev):
                events.append(ev)

            agent.turn(
                session_id="s1",
                request="сгенерируй кота и увеличь его",
                on_chain_step=_collector,
            )

    # Проверяем что события chain_step пришли с total_steps=2
    assert len(events) == 2
    assert events[0]["total_steps"] == 2
    assert events[1]["total_steps"] == 2
    assert events[0]["capability"] == "image.generate"
    assert events[1]["capability"] == "image.upscale"


# --- Integration test: run_turn → agent.turn → chain → stream.push ---

def test_run_turn_pushes_chain_step_events_to_stream(tmp_path):
    from app.ui import ComfyUIServer
    store = AssetStore(root=tmp_path)
    agent = ConversationAgent(store)
    server = ComfyUIServer(store=store, agent=agent)

    # Мокаем agent.turn чтобы он вызывал переданный on_chain_step
    def _mock_turn(
        self, session_id, request, on_chain_step=None, **_kw
    ):
        if on_chain_step:
            on_chain_step({
                "type": "chain_step",
                "step": 0,
                "total_steps": 2,
                "state": "completed",
                "capability": "image.generate",
                "outputs": ["asset1"],
            })
            on_chain_step({
                "type": "chain_step",
                "step": 1,
                "total_steps": 2,
                "state": "completed",
                "capability": "image.upscale",
                "outputs": ["asset2"],
            })
        return Job(
            prompt_id="p1",
            workflow_id="txt2img",
            version="1.0.0",
            capability="image.upscale",
            state=JobState.SUCCESS,
            output_assets=["asset2"],
        )

    # Заменяем agent.turn
    with patch.object(agent, "turn", side_effect=_mock_turn):
        # Запускаем run_turn
        server.run_turn(
            session_id="s1",
            request="сгенерируй кота и увеличь его",
        )

        # Читаем события через stream.wait_next
        stream = server.stream("s1")
        ev1 = stream.wait_next(0, timeout=1)
        ev2 = stream.wait_next(1, timeout=1)

        # Проверяем что события chain_step пришли с total_steps=2
        assert ev1["type"] == "chain_step"
        assert ev1["total_steps"] == 2
        assert ev1["capability"] == "image.generate"
        assert ev2["type"] == "chain_step"
        assert ev2["total_steps"] == 2
        assert ev2["capability"] == "image.upscale"
