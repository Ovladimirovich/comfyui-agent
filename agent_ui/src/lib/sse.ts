/**
 * SSE-клиент к Agent Core /events. Чистые функции без React.
 * Frontend НЕ вычисляет состояние агента — только подписывается на события,
 * которые backend уже стримит (start/status/progress/chain_step/result/error).
 */

import type { SSEMessage, SessionSnapshot, SnapshotMessage } from "./types";

/** URL поточных событий сессии. */
export function eventsUrl(sessionId: string): string {
  return `/events?session_id=${encodeURIComponent(sessionId)}`;
}

/** Парс события SSE из EventSource (EventSource сам обрабатывает event: name). */
export function parseSSEEvent(raw: string): SSEMessage {
  return JSON.parse(raw) as SSEMessage;
}

/** Восстановить исходное состояние после reload: /api/session snapshot. */
export function initialFromSnapshot(snap: SessionSnapshot): {
  dialogState: string | null;
  activeAsset: string | null;
  activeJob: string | null;
} {
  return {
    dialogState: snap.dialog_state ?? null,
    activeAsset: snap.active_asset ?? null,
    activeJob: snap.active_job ?? null,
  };
}

/** Определить, есть ли активный RUNNING Job (для продолжения recovery). */
export function hasRunningJob(snap: SessionSnapshot): boolean {
  return Boolean(snap.active_job);
}

/** Сгенерировать цепочку сообщений чата из snapshot (recovery после reload). */
export function messagesFromSnapshot(snap: SessionSnapshot): {
  role: "user" | "agent" | "system" | "error";
  text: string;
  state: string | null;
  jobId: string | null;
  error: string | null;
  assets: string[];
}[] {
  const out: ReturnType<typeof messagesFromSnapshot> = [];
  for (const m of (snap.messages ?? []) as SnapshotMessage[]) {
    if (m.turn) {
      // успешный ход: запрос пользователя + результат агента
      out.push({ role: "user", text: m.turn, state: "SUCCESS", jobId: m.job ?? null, error: null, assets: m.outputs ?? [] });
      out.push({
        role: "agent",
        text: `Выполнено (${m.capability ?? ""}${m.workflow ? ` · ${m.workflow}` : ""})`,
        state: "SUCCESS",
        jobId: m.job ?? null,
        error: null,
        assets: m.outputs ?? [],
      });
    } else if (m.type === "decision_failed") {
      out.push({
        role: "error",
        text: `Не выполнено${m.reason ? `: ${m.reason}` : ""}`,
        state: "FAILED",
        jobId: m.job ?? null,
        error: m.reason ?? null,
        assets: [],
      });
    } else if (m.type === "feedback_request") {
      out.push({
        role: "agent",
        text: `Требуется уточнение: ${m.reason ?? ""}`,
        state: "RUNNING",
        jobId: m.job ?? null,
        error: null,
        assets: [],
      });
    } else if (m.type === "retry_started" || m.type === "retry_completed") {
      out.push({
        role: "system",
        text: m.type === "retry_started" ? `Повторная попытка… (${m.attempt ?? "?"})` : `Retry завершён (${m.state ?? m.attempt ?? ""})`,
        state: m.state ?? "RUNNING",
        jobId: m.job ?? null,
        error: null,
        assets: [],
      });
    } else if (m.type === "cancelled") {
      out.push({ role: "system", text: "Отменено", state: "CANCELLED", jobId: m.job ?? null, error: null, assets: [] });
    }
  }
  if (snap.dialog_state === "error") {
    for (const u of (snap.unresolved ?? []) as { turn?: string; error?: string }[]) {
      out.push({
        role: "error",
        text: `Задача провалена: ${u.error ?? "нет подробностей"}`,
        state: "FAILED",
        jobId: null,
        error: u.error ?? null,
        assets: [],
      });
    }
  }
  return out;
}