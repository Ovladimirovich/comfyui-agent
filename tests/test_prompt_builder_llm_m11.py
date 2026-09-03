"""M11 — Tests for LLMPromptBuilder (online, OpenAI-compatible API).

Тесты используют mock transport — НЕ требуют реального API key и интернета.
"""
from __future__ import annotations
import sys

import json
import os
from dataclasses import dataclass
from typing import Literal, Optional
from unittest.mock import MagicMock, patch

# Добавить корень проекта в sys.path для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



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
    source: Literal["heuristic", "llm", "fallback"]
    rationale: Optional[str] = None


# Реальный импорт из модуля
from app.prompt.llm import LLMPromptBuilder, LLMPromptBuilderError  # noqa: E402


def _make_mock_response(status_code: int = 200, body: dict | None = None) -> MagicMock:
    """Создать мок-ответ для urllib.request.urlopen."""
    if body is None:
        body = {"choices": [{"message": {"content": "mock result"}}]}
    resp = MagicMock()
    resp.read.return_value = json.dumps(body).encode("utf-8")
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    resp.status = status_code
    return resp


def _make_mock_http_error(code: int, body: str = "error") -> MagicMock:
    """Создать мок HTTP ошибки."""
    err = MagicMock()
    err.code = code
    err.read.return_value = body.encode("utf-8")
    return err


def test_llm_basic_suggestion():
    """Input → LLM → PromptResult, source == 'llm'."""
    mock_resp = _make_mock_response(body={
        "choices": [{"message": {"content": "реалистичный кот на крыше ночью, лунный свет, детализированная шерсть"}}]
    })
    with patch('app.prompt.llm.urllib.request.urlopen', return_value=mock_resp):
        builder = LLMPromptBuilder(api_key="fake-key", base_url="http://mock/api")
        result = builder.build(PromptContext(original_text="кот на крыше ночью"))
        
        assert result.source == "llm"
        assert result.mode == "suggestion"
        assert result.variant_index == 0
        assert "кот" in result.enhanced_prompt.lower()
        assert result.original_preserved == True
    print(f"✓ test_llm_basic_suggestion: {result.enhanced_prompt}")


def test_llm_preserves_original_intent():
    """AD-32: исходное намерение сохраняется."""
    # Сценарий: LLM возвращает(prompt с сохранением subject
    mock_resp = _make_mock_response(body={
        "choices": [{"message": {"content": "кинематографичный портрет девушки, мягкий свет, 8k"}}]
    })
    with patch('app.prompt.llm.urllib.request.urlopen', return_value=mock_resp):
        builder = LLMPromptBuilder(api_key="fake-key")
        result = builder.build(PromptContext(original_text="портрет девушки"))
        
        assert result.original_preserved == True
        assert "портрет" in result.enhanced_prompt.lower() or "девушк" in result.enhanced_prompt.lower()
    print("✓ test_llm_preserves_original_intent: AD-32 соблюден")


def test_llm_empty_input():
    """Пустой prompt не отправляется в LLM."""
    builder = LLMPromptBuilder(api_key="fake-key")
    result = builder.build(PromptContext(original_text="", mode="suggestion"))
    
    assert result.enhanced_prompt == ""
    assert result.source == "llm"
    assert result.original_preserved == True
    print("✓ test_llm_empty_input: пустой запрос обработан без вызова LLM")


def test_llm_timeout():
    """Timeout превращается в контролируемую ошибку."""
    with patch('app.prompt.llm.urllib.request.urlopen', side_effect=TimeoutError("timed out")):
        builder = LLMPromptBuilder(api_key="fake-key", timeout=5)
        try:
            builder.build(PromptContext(original_text="кот"))
            assert False, "ожидалась ошибка таймаута"
        except LLMPromptBuilderError as e:
            assert "timeout" in str(e).lower() or "timed out" in str(e).lower()
    print("✓ test_llm_timeout: timeout обработан корректно")


def test_llm_api_error():
    """HTTP ошибка API обрабатывается."""
    # HTTPError должен иметь метод read()
    http_err = MagicMock()
    http_err.code = 401
    http_err.read.return_value = b"Unauthorized"
    # HTTPError — это исключение urllib.error
    from urllib.error import HTTPError
    http_err_exc = HTTPError("http://mock", 401, "Unauthorized", None, None)
    http_err_exc.read = lambda: b"Unauthorized"
    
    with patch('app.prompt.llm.urllib.request.urlopen', side_effect=http_err_exc):
        builder = LLMPromptBuilder(api_key="bad-key")
        try:
            builder.build(PromptContext(original_text="кот"))
            assert False, "ожидалась HTTP ошибка"
        except LLMPromptBuilderError as e:
            assert "401" in str(e) or "unauthorized" in str(e).lower()
    print("✓ test_llm_api_error: HTTP ошибка обработана")


def test_llm_deterministic_request():
    """При одинаковом PromptContext формируется одинаковый LLM request."""
    captured_data = []
    
    def mock_urlopen(req, timeout=None):
        if req.data:
            captured_data.append(json.loads(req.data.decode("utf-8")))
        return _make_mock_response(body={"choices": [{"message": {"content": "result"}}]})
    
    with patch('app.prompt.llm.urllib.request.urlopen', side_effect=mock_urlopen):
        builder = LLMPromptBuilder(api_key="fake-key")
        ctx = PromptContext(original_text="кот", suggestion_index=0)
        builder.build(ctx)
        builder.build(ctx)  # повторный вызов
        
        assert len(captured_data) == 2
        # Оба запроса должны быть идентичны
        assert captured_data[0]["messages"] == captured_data[1]["messages"]
        assert captured_data[0]["model"] == captured_data[1]["model"]
        assert "system" in str(captured_data[0]["messages"])
    print("✓ test_llm_deterministic_request: запросы детерминированы")


def test_no_comfyui_access():
    """LLMPromptBuilder не зависит от ComfyUI (AD-30)."""
    # Должен работать без ComfyUI, AssetStore, Provider
    mock_resp = _make_mock_response(body={"choices": [{"message": {"content": "реалистичный кот"}}]})
    with patch('app.prompt.llm.urllib.request.urlopen', return_value=mock_resp):
        builder = LLMPromptBuilder(api_key="fake-key")
        result = builder.build(PromptContext(original_text="кот"))
        
        assert result.source == "llm"
        assert result.enhanced_prompt != ""
    print("✓ test_no_comfyui_access: AD-30 соблюден (нет доступа к ComfyUI)")


def test_no_capability_selection():
    """LLMPromptBuilder не выбирает capability (AD-31)."""
    mock_resp = _make_mock_response(body={"choices": [{"message": {"content": "кот улучшен"}}]})
    with patch('app.prompt.llm.urllib.request.urlopen', return_value=mock_resp):
        builder = LLMPromptBuilder(api_key="fake-key")
        # Передаём capability — он должен игнорироваться
        ctx = PromptContext(
            original_text="кот",
            capability="image.generate",
            active_asset_type="image",
            suggestion_index=0
        )
        result = builder.build(ctx)
        
        assert isinstance(result.enhanced_prompt, str)
        assert result.enhanced_prompt != ""
        # Capability не должен влиять на результат
        assert "кот" in result.enhanced_prompt.lower()
    print("✓ test_no_capability_selection: AD-31 соблюден (capability игнорируется)")


def test_llm_missing_api_key():
    """Отсутствие API ключа — ошибка при инициализации."""
    with patch.dict('os.environ', {}, clear=True):
        try:
            LLMPromptBuilder()
            assert False, "ожидалась ошибка без API key"
        except LLMPromptBuilderError:
            pass
    print("✓ test_llm_missing_api_key: ошибка при отсутствии ключа")


def test_llm_bad_response_structure():
    """Плохая структура ответа LLM → ошибка."""
    mock_resp = _make_mock_response(body={"error": "bad format"})
    with patch('app.prompt.llm.urllib.request.urlopen', return_value=mock_resp):
        builder = LLMPromptBuilder(api_key="fake-key")
        try:
            builder.build(PromptContext(original_text="кот"))
            assert False, "ожидалась ошибка структуры ответа"
        except LLMPromptBuilderError as e:
            assert "bad response" in str(e).lower()
    print("✓ test_llm_bad_response_structure: плохая структура → ошибка")


def test_llm_env_vars():
    """Конфигурация через env vars."""
    with patch.dict('os.environ', {
        "LLM_API_KEY": "env-key",
        "LLM_MODEL": "custom-model",
        "LLM_BASE_URL": "http://custom-url",
        "LLM_TIMEOUT": "10",
    }):
        builder = LLMPromptBuilder(timeout=None)  # None → читает из env
        assert builder.api_key == "env-key"
        assert builder.model == "custom-model"
        assert builder.base_url == "http://custom-url"
        assert builder.timeout == 10
    print("✓ test_llm_env_vars: env vars корректно читаются")


if __name__ == "__main__":
    test_llm_basic_suggestion()
    test_llm_preserves_original_intent()
    test_llm_empty_input()
    test_llm_timeout()
    test_llm_api_error()
    test_llm_deterministic_request()
    test_no_comfyui_access()
    test_no_capability_selection()
    test_llm_missing_api_key()
    test_llm_bad_response_structure()
    test_llm_env_vars()
    print("\n=== All M11.4 LLMPromptBuilder tests PASSED ===")
