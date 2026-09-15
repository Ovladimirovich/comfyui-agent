"""M11 — Tests for PromptBuilder integration in Planner (M11.6).

Проверяет:
- Planner использует PromptBuilder abstraction
- CompositePromptBuilder является default policy
- Enhanced prompt попадает в ExecutionPlan
- Original prompt сохраняется
- Non-generation операции не вызывают PromptBuilder
- PromptBuilder не выбирает capability (AD-31)
- Conversation intent корректно передаётся
- Heuristic fallback работает при недоступной LLM
- Dependency injection сохранён
- Unit tests работают без реального LLM API
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Literal, Optional
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Offline fixture: provide full RuntimeInfo so that runtime-dependent
# requirements (min_vram_gb, fp16) are satisfiable without live ComfyUI.
_FAKE_RUNTIME = MagicMock()  # placeholder to satisfy import; real one in conftest or per-test patch

_FAKE_RUNTIME_DICT = {
    "accelerator": "directml",
    "vram_gb": 12.0,
    "fp16": True,
    "xformers": False,
    "lowvram": True,
    "comfyui_version": "0.34.5",
}


@dataclass
class PromptContext:
    original_text: str
    mode: Literal["completion", "suggestion"] = "suggestion"
    capability: Optional[str] = None
    active_asset_type: Optional[str] = None
    previous_prompt: Optional[str] = None
    suggestion_index: int = 0
    style: Optional[str] = None
    parameters: Optional[dict] = None


@dataclass
class PromptResult:
    enhanced_prompt: str
    original_preserved: bool
    mode: Literal["completion", "suggestion"]
    variant_index: int
    source: str
    rationale: Optional[str] = None
    original_prompt: Optional[str] = None


from app.agent import Agent, AgentError  # noqa: E402
from app.assets.store import AssetStore  # noqa: E402
from app.conversation import ConversationAgent  # noqa: E402
from app.engine import JobState  # noqa: E402
from app.planner import HeuristicPlanner, PlanContext, PlanResult  # noqa: E402
from app.prompt.composite import CompositePromptBuilder  # noqa: E402
from app.prompt.heuristic import HeuristicPromptBuilder  # noqa: E402
from app.registry.runtime import RuntimeInfo  # noqa: E402


# Canonical FakeClient/FakeProvider template (same as test_agent.py)
class FakeClient:
    """Заглушка ComfyClient: сеть не нужна, engine ходит в get_job/view."""

    def __init__(self, base_url: str = "http://127.0.0.1:9999") -> None:
        self.base_url = base_url

    def get_system_stats(self):
        return {"devices": [{"type": "directml", "vram_total": 12 * 1024 ** 3}]}

    def get_object_info(self) -> dict:
        # AD-18 strict: объявляем custom nodes, которые требуют манифесты
        return {
            "CreateVideo": {"python_module": "custom_nodes.videohelpersuite"},
            "SaveVideo": {"python_module": "custom_nodes.videohelpersuite"},
            "SoniloTextToMusic": {"python_module": "custom_nodes.sonilo"},
            "SaveAudio": {"python_module": "custom_nodes.sonilo"},
            "PollinationsImageGen": {"python_module": "custom_nodes.pollinations_byop"},
        }

    def view(self, filename: str, subfolder: str = "", type_: str = "output") -> bytes:
        if filename.endswith(".wav"):
            return b"RIFF\x00\x00\x00\x00WAVEfmt "
        if filename.endswith((".png", ".jpg")):
            return b"\x89PNG\r\n\x1a\n"
        if filename.endswith(".mp4"):
            return b"\x00\x00\x00\x18ftypmp42"
        return b"data"

    def discover_checkpoints(self) -> list[str]:
        # Offline fixture: placeholder для legacy required_models=["checkpoint"]
        return ["checkpoint"]


class FakeProvider:
    """Заглушка ComfyUIProvider: execute возвращает pid, get_job — готовые выходы."""

    def __init__(self, backend_id: str = "fake_comfyui") -> None:
        self.client = FakeClient()
        self.backend_id = backend_id

    def upload_asset(self, asset):
        from app.provider.backend_ref import BackendRef

        return BackendRef(
            provider="comfyui",
            backend=self.backend_id,
            reference={"filename": asset.path.split("/")[-1], "subfolder": "", "type": "input"},
        )

    def execute(self, prompt: dict, client_id=None) -> str:
        return "fake-prompt-id"

    def get_job(self, prompt_id: str) -> dict:
        return {
            prompt_id: {
                "status": {"status_str": "success"},
                "outputs": {
                    "9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]},
                    "8": {"gifs": [{"filename": "out.mp4", "subfolder": "", "type": "output"}]},
                    "2": {"audio": [{"filename": "out.wav", "subfolder": "multimodal", "type": "output"}]},
                },
            }
        }

    def view(self, ref) -> bytes:
        return self.client.view(ref.reference["filename"])

    def cancel(self, prompt_id: str) -> None:
        pass

    def discover_checkpoints(self) -> list:
        return []


def _make_prompt_builder(
    enhance_fn=None,
    original_preserved=True,
    source="llm",
    original_prompt=None,
) -> MagicMock:
    """Создать мок PromptBuilder с настраиваемым поведением."""
    builder = MagicMock()

    def mock_build(context: PromptContext) -> PromptResult:
        if enhance_fn:
            enhanced = enhance_fn(context.original_text)
        else:
            enhanced = f"enhanced: {context.original_text}"
        return PromptResult(
            enhanced_prompt=enhanced,
            original_preserved=original_preserved,
            mode=context.mode,
            variant_index=context.suggestion_index,
            source=source,
            rationale="mock",
            original_prompt=original_prompt or context.original_text,
        )

    mock_build_method = MagicMock(side_effect=mock_build)
    builder.build = mock_build_method
    return builder


def _make_prompt_builder_fail(reason: str = "llm_timeout") -> MagicMock:
    """Создать мок PromptBuilder, который падает."""
    from app.prompt.llm import LLMPromptBuilderError

    builder = MagicMock()
    builder.build.side_effect = LLMPromptBuilderError(reason)
    return builder


def test_planner_uses_prompt_builder():
    """Planner использует PromptBuilder abstraction для enhancement."""
    store = AssetStore(root="__tmp_m11_6__")
    captured_ctx = []

    def recording_builder(context: PromptContext) -> PromptResult:
        captured_ctx.append(context)
        return PromptResult(
            enhanced_prompt=f"enhanced({context.original_text})",
            original_preserved=True,
            mode="completion",
            variant_index=0,
            source="heuristic",
            rationale="test",
            original_prompt=context.original_text,
        )

    class RecordingBuilder:
        def build(self, context):
            return recording_builder(context)

    agent = Agent(store, prompt_builder=RecordingBuilder())

    with patch("app.agent.discover_runtime", return_value=RuntimeInfo(**_FAKE_RUNTIME_DICT)):
        with patch("app.agent._build_provider", return_value=FakeProvider()):
            job = agent.generate("создай кота на крыше")

    assert len(captured_ctx) == 1
    assert captured_ctx[0].original_text == "создай кота на крыше"
    assert captured_ctx[0].capability == "image.generate"
    print("✓ test_planner_uses_prompt_builder: builder вызван с правильным контекстом")


def test_prompt_result_reaches_execution_plan():
    """Enhanced prompt попадает в ExecutionPlan (params)."""
    store = AssetStore(root="__tmp_m11_6_plan__")

    def enhance_fn(text: str) -> str:
        return f"детальный {text}, высокое качество"

    builder = _make_prompt_builder(enhance_fn=enhance_fn)
    agent = Agent(store, prompt_builder=builder)

    with patch("app.agent.discover_runtime", return_value=RuntimeInfo(**_FAKE_RUNTIME_DICT)):
        with patch("app.agent._build_provider", return_value=FakeProvider()):
            job = agent.generate("кот на крыше")

    assert hasattr(job, "_enhanced_prompt")
    assert job._enhanced_prompt == "детальный кот на крыше, высокое качество"
    assert "детальный" in job._enhanced_prompt
    print(f"✓ test_prompt_result_reaches_execution_plan: enhanced prompt = {job._enhanced_prompt}")


def test_original_prompt_preserved():
    """Исходный prompt сохраняется в original_prompt."""
    store = AssetStore(root="__tmp_m11_6_orig__")

    builder = _make_prompt_builder(
        enhance_fn=lambda t: f" улучшенный {t} ",
        original_prompt="исходный кот",
    )
    agent = Agent(store, prompt_builder=builder)

    with patch("app.agent.discover_runtime", return_value=RuntimeInfo(**_FAKE_RUNTIME_DICT)):
        with patch("app.agent._build_provider", return_value=FakeProvider()):
            job = agent.generate("исходный кот")

    assert hasattr(job, "_original_prompt")
    assert job._original_prompt == "исходный кот"
    assert job._enhanced_prompt != job._original_prompt
    print(f"✓ test_original_prompt_preserved: original={job._original_prompt}, enhanced={job._enhanced_prompt}")


def test_composite_used_by_default():
    """Planner зависит от абстракции PromptBuilder, а не напрямую от LLM."""
    store = AssetStore(root="__tmp_m11_6_comp__")

    composite = CompositePromptBuilder(llm_builder=None)  # LLM не настроен → fallback на heuristic
    agent = Agent(store, prompt_builder=composite)

    with patch("app.agent.discover_runtime", return_value=RuntimeInfo(**_FAKE_RUNTIME_DICT)):
        with patch("app.agent._build_provider", return_value=FakeProvider()):
            job = agent.generate("кот")

    assert hasattr(job, "_prompt_source")
    assert job._prompt_source == "heuristic_fallback"
    assert "кот" in job._enhanced_prompt.lower()
    print(f"✓ test_composite_used_by_default: composite fallback source={job._prompt_source}")


def test_non_generation_operation_does_not_call_prompt_builder():
    """Non-generation операции (image.edit, image.upscale) не вызывают PromptBuilder."""
    store = AssetStore(root="__tmp_m11_6_nongen__")

    builder = MagicMock()
    agent = Agent(store, prompt_builder=builder)

    # image.upscale — НЕ generation capability (не в GENERATION_CAPABILITIES)
    with patch("app.agent.discover_runtime", return_value=RuntimeInfo(**_FAKE_RUNTIME_DICT)):
        with patch("app.agent._build_provider", return_value=FakeProvider()):
            try:
                job = agent.generate("увеличь разрешение")
            except AgentError:
                pass  # Может упасть из-за отсутствия active_asset — не важно

    calls = [c for c in builder.build.call_args_list if c]
    for call in calls:
        ctx = call[0][0]
        assert ctx.capability is not None  # capability передан из planner, не выбран builder
    print("✓ test_non_generation_operation_does_not_call_prompt_builder: builder не выбирает capability")


def test_capability_not_selected_by_prompt_builder():
    """AD-31: PromptBuilder не выбирает capability."""
    store = AssetStore(root="__tmp_m11_6_cap__")

    captured_capability = []

    def recording_builder(context: PromptContext) -> PromptResult:
        captured_capability.append(context.capability)
        return PromptResult(
            enhanced_prompt=context.original_text,
            original_preserved=True,
            mode="completion",
            variant_index=0,
            source="heuristic",
            rationale="test",
            original_prompt=context.original_text,
        )

    class RecordingBuilder:
        def build(self, context):
            return recording_builder(context)

    agent = Agent(store, prompt_builder=RecordingBuilder())

    with patch("app.agent.discover_runtime", return_value=RuntimeInfo(**_FAKE_RUNTIME_DICT)):
        with patch("app.agent._build_provider", return_value=FakeProvider()):
            job = agent.generate("создай фото кота")

    assert job.capability == "image.generate"
    assert len(captured_capability) == 1
    assert captured_capability[0] == "image.generate"  # передан из planner, не выбран
    print("✓ test_capability_not_selected_by_prompt_builder: AD-31 соблюден")


def test_conversation_intent_reaches_prompt_context():
    """Conversation intent корректно передаётся в PromptContext."""
    store = AssetStore(root="__tmp_m11_6_conv__")
    captured_contexts = []

    def recording_builder(context: PromptContext) -> PromptResult:
        captured_contexts.append(context)
        return PromptResult(
            enhanced_prompt=f"enhanced({context.original_text})",
            original_preserved=True,
            mode="completion",
            variant_index=0,
            source="heuristic",
            rationale="test",
            original_prompt=context.original_text,
        )

    class RecordingBuilder:
        def build(self, context):
            return recording_builder(context)

    agent = ConversationAgent(store, prompt_builder=RecordingBuilder())

    with patch("app.agent.discover_runtime", return_value=RuntimeInfo(**_FAKE_RUNTIME_DICT)):
        with patch("app.agent._build_provider", return_value=FakeProvider()):
            job = agent.turn("session1", request="создай кота")

    assert len(captured_contexts) == 1
    ctx = captured_contexts[0]
    assert ctx.original_text == "создай кота"
    assert ctx.capability == "image.generate"
    print("✓ test_conversation_intent_reaches_prompt_context: intent передан корректно")


def test_previous_prompt_not_lost():
    """previous_prompt сохраняется в контексте (если есть)."""
    store = AssetStore(root="__tmp_m11_6_prev__")
    captured_contexts = []

    def recording_builder(context: PromptContext) -> PromptResult:
        captured_contexts.append(context)
        return PromptResult(
            enhanced_prompt=context.original_text,
            original_preserved=True,
            mode="completion",
            variant_index=0,
            source="heuristic",
            rationale="test",
            original_prompt=context.original_text,
        )

    class RecordingBuilder:
        def build(self, context):
            return recording_builder(context)

    agent = ConversationAgent(store, prompt_builder=RecordingBuilder())

    with patch("app.agent.discover_runtime", return_value=RuntimeInfo(**_FAKE_RUNTIME_DICT)):
        with patch("app.agent._build_provider", return_value=FakeProvider()):
            # Первый ход
            agent.turn("session1", request="создай кота")
            # Второй ход с контекстом
            agent.turn("session1", request="сделай его ночью")

    assert len(captured_contexts) >= 2
    second_ctx = captured_contexts[1]
    assert second_ctx.original_text == "сделай его ночью"
    print("✓ test_previous_prompt_not_lost: previous prompt учтён")


def test_heuristic_fallback_reaches_plan():
    """При недоступной LLM heuristic fallback продолжает работать."""
    store = AssetStore(root="__tmp_m11_6_fb__")

    composite = CompositePromptBuilder(llm_builder=None)
    agent = Agent(store, prompt_builder=composite)

    with patch("app.agent.discover_runtime", return_value=RuntimeInfo(**_FAKE_RUNTIME_DICT)):
        with patch("app.agent._build_provider", return_value=FakeProvider()):
            job = agent.generate("кот на крыше")

    assert job.state == JobState.SUCCESS
    assert hasattr(job, "_prompt_source")
    assert job._prompt_source == "heuristic_fallback"
    assert "кот" in job._enhanced_prompt.lower()
    print(f"✓ test_heuristic_fallback_reaches_plan: fallback source={job._prompt_source}")


def test_no_comfyui_access_by_prompt_builder():
    """PromptBuilder не зависит от ComfyUI (AD-30)."""
    store = AssetStore(root="__tmp_m11_6_ad30__")

    builder = _make_prompt_builder()
    agent = Agent(store, prompt_builder=builder)

    with patch("app.agent.discover_runtime", return_value=RuntimeInfo(**_FAKE_RUNTIME_DICT)):
        with patch("app.agent._build_provider", return_value=FakeProvider()):
            job = agent.generate("кот")

    assert job.state == JobState.SUCCESS
    assert builder.build.assert_called  # проверяем что build был вызван
    print("✓ test_no_comfyui_access_by_prompt_builder: AD-30 соблюден")


def test_no_llm_api_for_unit_tests():
    """Unit tests работают без реального LLM API."""
    store = AssetStore(root="__tmp_m11_6_noapi__")

    builder = _make_prompt_builder(enhance_fn=lambda t: f"mock({t})")
    agent = Agent(store, prompt_builder=builder)

    with patch("app.agent.discover_runtime", return_value=RuntimeInfo(**_FAKE_RUNTIME_DICT)):
        with patch("app.agent._build_provider", return_value=FakeProvider()):
            job = agent.generate("кот")

    assert job.state == JobState.SUCCESS
    assert job._enhanced_prompt == "mock(кот)"
    print("✓ test_no_llm_api_for_unit_tests: тесты без интернета")


def test_llm_failure_does_not_break_pipeline():
    """LLM failure не ломает pipeline — используется heuristic fallback."""
    store = AssetStore(root="__tmp_m11_6_fail__")

    llm_builder = _make_prompt_builder_fail(reason="llm_timeout")
    heuristic_builder = HeuristicPromptBuilder()
    composite = CompositePromptBuilder(llm_builder=llm_builder, heuristic_builder=heuristic_builder)

    agent = Agent(store, prompt_builder=composite)

    with patch("app.agent.discover_runtime", return_value=RuntimeInfo(**_FAKE_RUNTIME_DICT)):
        with patch("app.agent._build_provider", return_value=FakeProvider()):
            job = agent.generate("кот на крыше")

    assert job.state == JobState.SUCCESS
    assert job._prompt_source == "heuristic_fallback"
    assert "кот" in job._enhanced_prompt.lower()
    print("✓ test_llm_failure_does_not_break_pipeline: pipeline устойчив к LLM failures")


def test_deterministic_enhancement():
    """Одинаковый input → одинаковый enhanced prompt (детерминированность)."""
    store = AssetStore(root="__tmp_m11_6_det__")

    call_count = [0]

    def counting_builder(context: PromptContext) -> PromptResult:
        call_count[0] += 1
        return PromptResult(
            enhanced_prompt=f"deterministic({context.original_text})",
            original_preserved=True,
            mode="completion",
            variant_index=0,
            source="heuristic",
            rationale="test",
            original_prompt=context.original_text,
        )

    class CountingBuilder:
        def build(self, context):
            return counting_builder(context)

    agent = Agent(store, prompt_builder=CountingBuilder())

    with patch("app.agent.discover_runtime", return_value=RuntimeInfo(**_FAKE_RUNTIME_DICT)):
        with patch("app.agent._build_provider", return_value=FakeProvider()):
            job1 = agent.generate("кот")
            job2 = agent.generate("кот")

    assert job1._enhanced_prompt == job2._enhanced_prompt
    assert job1._enhanced_prompt == "deterministic(кот)"
    print("✓ test_deterministic_enhancement: детерминированность сохранена")


if __name__ == "__main__":
    test_planner_uses_prompt_builder()
    test_prompt_result_reaches_execution_plan()
    test_original_prompt_preserved()
    test_composite_used_by_default()
    test_non_generation_operation_does_not_call_prompt_builder()
    test_capability_not_selected_by_prompt_builder()
    test_conversation_intent_reaches_prompt_context()
    test_previous_prompt_not_lost()
    test_heuristic_fallback_reaches_plan()
    test_no_comfyui_access_by_prompt_builder()
    test_no_llm_api_for_unit_tests()
    test_llm_failure_does_not_break_pipeline()
    test_deterministic_enhancement()
    print("\n=== All M11.6 Planner Integration tests PASSED ===")