/**
 * Типы контрактов Agent Core (backend app/ui.py), зеркалирующие реальные
 * payload'ы SSE-событий и §21 API. Frontend НЕ порождает своих состояний —
 * только типизация того, что приходит с сервера.
 */

/** Ответ POST /api/chat и /turn. */
export interface ChatResponse {
  ok: boolean;
  session_id: string;
  endpoint?: string;
}

/** Статус Job — GET /api/jobs/{id} (PROJECT_SPEC §21). */
export interface JobStatus {
  prompt_id: string;
  capability: string;
  params: Record<string, unknown>;
  workflow_id: string;
  workflow_version: string;
  state: "QUEUED" | "RUNNING" | "SUCCESS" | "FAILED" | "CANCELLED";
  progress_pct: number | null;
  attempt: number;
  duration: number;
  error: string | null;
  error_class: string | null;
  output_assets: string[];
  chain_id: string | null;
  chain_step_index: number | null;
  backend_execution_identity: string | null;
  timestamp: number;
}

/** SSE-событие из /events (существующие типы backend, без новых). */
export interface SSEMessage {
  type: "start" | "status" | "progress" | "chain_step" | "result" | "error";
  [key: string]: unknown;
}

/** Запись из ConversationContext.messages (snapshot /api/session). */
export interface SnapshotMessage {
  turn?: string;
  capability?: string;
  workflow?: string;
  job?: string;
  outputs?: string[];
  active_asset?: string;
  attempt?: number;
  type?: string;
  state?: string;
  reason?: string;
  suggestions?: string[];
  missing_inputs?: string[];
  error?: string;
}

/** Событие result из /events. */
export interface ResultEvent {
  type: "result";
  state?: string | null;
  active_asset?: string | null;
  active_workflow?: string | null;
  active_job?: string | null;
  assets?: string[];
  job?: string | null;
  error?: string | null;
  error_class?: string | null;
  preview?: string | null;
}

/** Событие error из /events. */
export interface ErrorEvent {
  type: "error";
  error?: string;
  kind?: string;
}

/** Snapshot сессии — GET /api/session. */
export interface SessionSnapshot {
  session_id?: string;
  exists?: boolean;
  dialog_state?: string;
  active_asset?: string | null;
  active_job?: string | null;
  active_workflow?: string | null;
  messages?: unknown[];
  assets?: string[];
  jobs?: string[];
  unresolved?: unknown[];
}