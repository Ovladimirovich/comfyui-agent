"""M13+M22+M23 — Retry Policy + Decision Bridge + Parameter Adjustment.

RetryPolicy определяет, следует ли повторять попытку execution.
CorrectionStrategy определяет, какие параметры менять при повторе.

Usage:
    policy = RetryPolicy(max_attempts=3)
    decision = policy.decide(state, attempt, error_class)
    if decision.action == "retry":
        params = {**params, **decision.param_adjustments}  # M23
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# Классы ошибок (error_class в Job/ExecutionRecord)
ERROR_TRANSIENT = "transient"      # временная ошибка (timeout, WS disconnect)
ERROR_PERMANENT = "permanent"      # постоянная ошибка (missing model, invalid workflow)
ERROR_VERIFICATION = "verification"  # верификация не пройдена (битый output)


def classify_error(error_message: str) -> str:
    """Классифицировать ошибку по сообщению.

    transient: timeout, connection, WebSocket, temporary
    permanent: missing, invalid, not found, permission
    verification: signature, empty, corrupted
    """
    msg = error_message.lower()

    # Verification errors (битый output)
    if any(kw in msg for kw in ("сигнатур", "empty", "пустой", "corrupted", "неверный формат")):
        return ERROR_VERIFICATION

    # Transient errors (временные)
    if any(kw in msg for kw in (
        "timeout", "таймаут", "timed out",
        "connection", "соединение", "connection refused",
        "websocket", "ws", "разорван",
        "temporary", "временно",
        "busy", "занят",
        "queue", "очередь",
    )):
        return ERROR_TRANSIENT

    # Permanent errors (постоянные)
    if any(kw in msg for kw in (
        "not found", "не найден", "missing",
        "invalid", "невалид", "некоррект",
        "permission", "доступ",
        "forbidden", "запрещён",
        "model", "модель",
        "workflow", "capability не найден",
    )):
        return ERROR_PERMANENT

    # По умолчанию — transient (попробуем ещё раз)
    return ERROR_TRANSIENT


# ---------------------------------------------------------------------------
# M23: Parameter Adjustment Strategy
# ---------------------------------------------------------------------------

@dataclass
class CorrectionStrategy:
    """Стратегия корректировки параметров при конкретном типе ошибки.

    error_class: класс ошибки (transient/permanent/verification)
    adjust_fn: функция корректировки (params, semantic_score) → adjusted_params
    description: описание стратегии (для логов/диагностики)
    """
    error_class: str
    adjust_fn: Callable[[dict, float | None], dict]
    description: str = ""


def _adjust_steps_down(params: dict, semantic_score: float | None = None) -> dict:
    """Уменьшить steps при низком semantic score (< 0.3)."""
    steps = params.get("steps", 20)
    new_steps = max(5, int(steps * 0.7))
    return {**params, "steps": new_steps}


def _adjust_steps_up(params: dict, semantic_score: float | None = None) -> dict:
    """Увеличить steps при среднем semantic score (0.3-0.7)."""
    steps = params.get("steps", 20)
    new_steps = min(50, int(steps * 1.3))
    return {**params, "steps": new_steps}


def _adjust_timeout(params: dict, semantic_score: float | None = None) -> dict:
    """Увеличить timeout при transient timeout ошибке."""
    timeout = params.get("timeout", 120)
    return {**params, "timeout": min(300, int(timeout * 1.5))}


def _adjust_image_size_down(params: dict, semantic_score: float | None = None) -> dict:
    """Уменьшить размер изображения при timeout/перегрузке."""
    w = params.get("width", 512)
    h = params.get("height", 512)
    scale = 0.75
    return {**params, "width": max(256, int(w * scale)), "height": max(256, int(h * scale))}


def _adjust_cfg(params: dict, semantic_score: float | None = None) -> dict:
    """Скорректировать CFG при verification ошибке."""
    cfg = params.get("cfg", 7.0)
    if semantic_score is not None and semantic_score < 0.3:
        new_cfg = max(3.0, cfg - 2.0)
    else:
        new_cfg = min(12.0, cfg + 1.0)
    return {**params, "cfg": new_cfg}


# Встроенные стратегии (адаптивные по error_class + semantic_score)
DEFAULT_CORRECTION_STRATEGIES: list[CorrectionStrategy] = [
    # Verification: score < 0.3 → уменьшить steps, иначе увеличить
    CorrectionStrategy(
        error_class=ERROR_VERIFICATION,
        adjust_fn=lambda p, s: _adjust_steps_down(p, s) if s is not None and s < 0.3 else _adjust_steps_up(p, s),
        description="adjust steps based on semantic score",
    ),
    # Verification: скорректировать CFG
    CorrectionStrategy(
        error_class=ERROR_VERIFICATION,
        adjust_fn=_adjust_cfg,
        description="adjust CFG based on semantic score",
    ),
    # Transient timeout: увеличить timeout
    CorrectionStrategy(
        error_class=ERROR_TRANSIENT,
        adjust_fn=_adjust_timeout,
        description="increase timeout on transient error",
    ),
]


@dataclass
class RetryDecision:
    """Решение о повторе.

    action: "accept" | "retry" | "failed"
    reason: текстовое описание причины
    delay: задержка до следующей попытки (секунды)
    suggestions: подсказки для пользователя (при action="failed")
    param_adjustments: рекомендованные изменения параметров (при action="retry")
    """
    action: str  # "accept" | "retry" | "failed"
    reason: str = ""
    delay: float = 0.0  # секунды до следующей попытки
    suggestions: list[str] = field(default_factory=list)  # M22: подсказки для пользователя
    param_adjustments: dict | None = None  # M23: рекомендованные изменения параметров


@dataclass
class RetryPolicy:
    """Политика повтора при неудаче.

    max_attempts: максимальное количество попыток (включая первую)
    backoff_base: базовая задержка между попытками (секунды)
    backoff_max: максимальная задержка (секунды)
    retryable_errors: множества error_class, при которых возможен retry
    correction_strategies: стратегии корректировки параметров (M23)
    feedback_store: хранилище feedback (M24) — для оценки удовлетворённости
    session_id: ID сессии (M24) — для lookup feedback
    """

    max_attempts: int = 3
    backoff_base: float = 1.0
    backoff_max: float = 30.0
    retryable_errors: set[str] = field(
        default_factory=lambda: {ERROR_TRANSIENT, ERROR_VERIFICATION}
    )
    correction_strategies: list[CorrectionStrategy] = field(
        default_factory=lambda: list(DEFAULT_CORRECTION_STRATEGIES)
    )
    feedback_store: Any = None  # M24: Optional[FeedbackStore]
    session_id: str | None = None  # M24: для lookup feedback
    low_rating_threshold: int = 2  # M24: rating <= threshold → ask_user

    def decide(
        self,
        state: str,
        attempt: int,
        error_class: str | None = None,
        current_params: dict | None = None,  # M23: текущие параметры для корректировки
        semantic_score: float | None = None,  # M23: semantic score от верификации
        prompt_id: str | None = None,  # M24: для lookup feedback
        session_id: str | None = None,  # M24.1: ID сессии для feedback lookup
        feedback_store: Any = None,  # M24.1: хранилище feedback (приоритет над self.feedback_store)
    ) -> RetryDecision:
        """Решить: принять, повторить или зафиксировать неуспех.

        Args:
            state: текущее состояние Job (SUCCESS/FAILED/CANCELLED)
            attempt: номер текущей попытки (1-based)
            error_class: класс ошибки (transient/permanent/verification)
            current_params: текущие параметры execution (для M23 корректировки)
            semantic_score: score от SemanticVerifier (для M23 корректировки)
            prompt_id: ID попытки (для M24 feedback lookup)
            session_id: ID сессии (для M24.1 feedback lookup)
            feedback_store: хранилище feedback (M24.1, приоритет над self.feedback_store)

        Returns:
            RetryDecision с action: "accept" | "retry" | "failed" | "ask_user"
        """
        # M24.1: резолвим feedback_store (parameter > self.feedback_store)
        effective_fb_store = feedback_store or self.feedback_store
        # M24.1: резолвим session_id (parameter > self.session_id)
        effective_session = session_id or self.session_id

        # Успех — принять (с проверкой feedback, M24)
        if state == "SUCCESS":
            # M24: проверяем feedback пользователя
            ask = self._check_feedback_after_success(prompt_id, effective_fb_store, effective_session)
            if ask is not None:
                return ask
            return RetryDecision(action="accept", reason="execution succeeded")

        # Отмена — не повторяем
        if state == "CANCELLED":
            return RetryDecision(
                action="failed",
                reason="execution cancelled",
                suggestions=["отправьте запрос заново"],
            )

        # Неуспех — классифицируем
        if state == "FAILED":
            # Постоянная ошибка — не повторяем
            if error_class == ERROR_PERMANENT:
                return RetryDecision(
                    action="failed",
                    reason=f"permanent error: {error_class}",
                    suggestions=[
                        "проверьте доступность модели",
                        "проверьте конфигурацию workflow",
                        "убедитесь что required custom nodes установлены",
                    ],
                )

            # Исчерпаны попытки
            if attempt >= self.max_attempts:
                return RetryDecision(
                    action="failed",
                    reason=f"max attempts ({self.max_attempts}) reached",
                    suggestions=[
                        "попробуйте изменить промпт",
                        "уменьшите сложность запроса",
                        "измените параметры (steps, width, height)",
                    ],
                )

            # Повторяемая ошибка — повторяем с backoff + M23 param_adjustments
            if error_class in self.retryable_errors or error_class is None:
                delay = self._backoff(attempt)
                adjustments = self._compute_adjustments(
                    error_class, current_params, semantic_score
                )
                return RetryDecision(
                    action="retry",
                    reason=f"retryable error: {error_class or 'unknown'}",
                    delay=delay,
                    param_adjustments=adjustments,
                )

            # Неизвестный класс ошибки — не повторяем
            return RetryDecision(
                action="failed",
                reason=f"unknown error class: {error_class}",
                suggestions=[
                    "проверьте логи ошибок",
                    "попробуйте снова позже",
                ],
            )

        # Неизвестное состояние — не повторяем
        return RetryDecision(
            action="failed",
            reason=f"unknown state: {state}",
            suggestions=["обратитесь к администратору"],
        )

    def _compute_adjustments(
        self,
        error_class: str | None,
        current_params: dict | None,
        semantic_score: float | None,
    ) -> dict | None:
        """Вычислить param_adjustments на основе стратегий (M23).

        Возвращает объединённые adjustments от всех matching стратегий,
        или None если нет стратегий или нет параметров для корректировки.
        """
        if not current_params or not self.correction_strategies:
            return None

        merged: dict = {}
        for strategy in self.correction_strategies:
            if strategy.error_class == error_class:
                try:
                    adjusted = strategy.adjust_fn(dict(current_params), semantic_score)
                    # Берём только изменённые ключи
                    for k, v in adjusted.items():
                        if v != current_params.get(k):
                            merged[k] = v
                except Exception:
                    # Стратегия упала — пропускаем, не крашим retry
                    continue

        return merged if merged else None

    def _backoff(self, attempt: int) -> float:
        """Экспоненциальный backoff с jitter.

        delay = min(backoff_base * 2^(attempt-1), backoff_max)
        """
        delay = self.backoff_base * (2 ** (attempt - 1))
        return min(delay, self.backoff_max)

    def _check_feedback_after_success(
        self,
        prompt_id: str | None,
        feedback_store: Any = None,
        session_id: str | None = None,
    ) -> RetryDecision | None:
        """M24: Проверить feedback после успешного execution.

        Если пользователь ранее поставил низкий rating (<= low_rating_threshold)
        на эту попытку — возвращаем action="ask_user" для запроса уточнения.

        Возвращает RetryDecision("ask_user") или None (нет feedback / rating нормальный).
        """
        fb_store = feedback_store or self.feedback_store
        sess_id = session_id or self.session_id
        if fb_store is None or sess_id is None or prompt_id is None:
            return None

        try:
            fb = fb_store.get_for_attempt(prompt_id, sess_id)
            if fb is not None and fb.rating <= self.low_rating_threshold:
                return RetryDecision(
                    action="ask_user",
                    reason=f"user rated {fb.rating}/5 after success",
                    suggestions=[
                        "уточните что не понравилось",
                        "опишите желаемый результат",
                        "попробуйте другой промпт",
                    ],
                )
        except Exception:
            # Feedback lookup не критичен — пропускаем
            pass

        return None
