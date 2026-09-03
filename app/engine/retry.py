"""M13 — Retry Policy: решение о повторе при неудаче.

RetryPolicy определяет, следует ли повторять попытку execution.

Usage:
    policy = RetryPolicy(max_attempts=3)
    decision = policy.decide(job, history)
    if decision.action == "retry":
        # повторить с теми же параметрами
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


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


@dataclass
class RetryDecision:
    """Решение о повторе."""
    action: str  # "accept" | "retry" | "failed"
    reason: str = ""
    delay: float = 0.0  # секунды до следующей попытки


@dataclass
class RetryPolicy:
    """Политика повтора при неудаче.

    max_attempts: максимальное количество попыток (включая первую)
    backoff_base: базовая задержка между попытками (секунды)
    backoff_max: максимальная задержка (секунды)
    retryable_errors: множества error_class, при которых возможен retry
    """

    max_attempts: int = 3
    backoff_base: float = 1.0
    backoff_max: float = 30.0
    retryable_errors: set[str] = field(
        default_factory=lambda: {ERROR_TRANSIENT, ERROR_VERIFICATION}
    )

    def decide(
        self,
        state: str,
        attempt: int,
        error_class: str | None = None,
    ) -> RetryDecision:
        """Решить: принять, повторить или зафиксировать неуспех.

        Args:
            state: текущее состояние Job (SUCCESS/FAILED/CANCELLED)
            attempt: номер текущей попытки (1-based)
            error_class: класс ошибки (transient/permanent/verification)

        Returns:
            RetryDecision с action: "accept" | "retry" | "failed"
        """
        # Успех — принять
        if state == "SUCCESS":
            return RetryDecision(action="accept", reason="execution succeeded")

        # Отмена — не повторяем
        if state == "CANCELLED":
            return RetryDecision(action="failed", reason="execution cancelled")

        # Неуспех — классифицируем
        if state == "FAILED":
            # Постоянная ошибка — не повторяем
            if error_class == ERROR_PERMANENT:
                return RetryDecision(
                    action="failed",
                    reason=f"permanent error: {error_class}",
                )

            # Исчерпаны попытки
            if attempt >= self.max_attempts:
                return RetryDecision(
                    action="failed",
                    reason=f"max attempts ({self.max_attempts}) reached",
                )

            # Повторяемая ошибка — повторяем с backoff
            if error_class in self.retryable_errors or error_class is None:
                delay = self._backoff(attempt)
                return RetryDecision(
                    action="retry",
                    reason=f"retryable error: {error_class or 'unknown'}",
                    delay=delay,
                )

            # Неизвестный класс ошибки — не повторяем
            return RetryDecision(
                action="failed",
                reason=f"unknown error class: {error_class}",
            )

        # Неизвестное состояние — не повторяем
        return RetryDecision(action="failed", reason=f"unknown state: {state}")

    def _backoff(self, attempt: int) -> float:
        """Экспоненциальный backoff с jitter.

        delay = min(backoff_base * 2^(attempt-1), backoff_max)
        """
        delay = self.backoff_base * (2 ** (attempt - 1))
        return min(delay, self.backoff_max)
