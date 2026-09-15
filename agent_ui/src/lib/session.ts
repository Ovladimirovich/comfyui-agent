/**
 * Управление session_id (localStorage). Чистые функции, тестируемые.
 * session_id — единственный ключ сессии; хранится в localStorage (как в app/ui.py).
 */

const KEY = "agent_ui_session_id";

/** Сгенерировать новый session_id. */
export function newSessionId(): string {
  return (
    Math.random().toString(36).slice(2) +
    Date.now().toString(36)
  );
}

/** Прочитать session_id из хранилища (localStorage-совместимый интерфейс). */
export function readSession(storage: Pick<Storage, "getItem" | "setItem">): string {
  const existing = storage.getItem(KEY);
  if (existing) return existing;
  const fresh = newSessionId();
  storage.setItem(KEY, fresh);
  return fresh;
}