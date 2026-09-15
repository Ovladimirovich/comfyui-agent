/**
 * API-клиент к Agent Core (app/ui.py). Чистые функции, без React.
 * Обращается к относительным путям (прокси Vite → 127.0.0.1:8189).
 * Никакой локальной state machine агента — только транспорт к backend контрактам.
 */

import type { ChatResponse, JobStatus } from "./types";

/** Запустить ход диалога через POST /api/chat (PROJECT_SPEC §21). */
export async function sendChat(
  sessionId: string,
  request: string,
  assets?: Record<string, unknown>,
): Promise<ChatResponse> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, request, assets }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as Record<string, unknown>).error as string || `chat failed: ${res.status}`);
  }
  return (await res.json()) as ChatResponse;
}

/** POST /api/assets — загрузка вложения (PROJECT_SPEC §21, S9). */
export async function uploadAsset(file: File): Promise<{ asset_id: string }> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch("/api/assets", { method: "POST", body: fd });
  const body = (await res.json().catch(() => ({}))) as { asset_id?: string; error?: string };
  if (!res.ok || !body.asset_id) throw new Error(body.error || `upload failed: ${res.status}`);
  return { asset_id: body.asset_id };
}

/** Запустить turn (обратная совместимость /turn). */
export function sendTurn(sessionId: string, request: string): Promise<ChatResponse> {
  return fetch("/turn", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, request }),
  }).then((r) => {
    if (!r.ok) throw new Error(`turn failed: ${r.status}`);
    return r.json() as Promise<ChatResponse>;
  });
}

/** Получить snapshot сессии (для recovery после reload). */
export async function sessionSnapshot(sessionId: string): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/session?session_id=${encodeURIComponent(sessionId)}`);
  if (!res.ok) throw new Error(`session failed: ${res.status}`);
  return (await res.json()) as Record<string, unknown>;
}

/** GET /api/jobs/{id} — статус Job (PROJECT_SPEC §21). */
export async function jobStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
  if (res.status === 404) throw new Error(`job ${jobId} not found`);
  if (!res.ok) throw new Error(`job status failed: ${res.status}`);
  return (await res.json()) as JobStatus;
}

/** GET /api/capabilities — список capabilities (PROJECT_SPEC §21). */
export async function capabilities(): Promise<string[]> {
  const res = await fetch("/api/capabilities");
  if (!res.ok) throw new Error(`capabilities failed: ${res.status}`);
  const body = (await res.json()) as { capabilities?: string[] };
  return body.capabilities ?? [];
}

/** GET /api/workflows — список workflows (PROJECT_SPEC §21). */
export async function workflows(): Promise<unknown[]> {
  const res = await fetch("/api/workflows");
  if (!res.ok) throw new Error(`workflows failed: ${res.status}`);
  const body = (await res.json()) as { workflows?: unknown[] };
  return body.workflows ?? [];
}

/** POST /api/jobs/{id}/cancel — отмена Job (PROJECT_SPEC §21). */
export async function cancelJob(jobId: string): Promise<void> {
  const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" });
  if (res.status === 404) throw new Error(`job ${jobId} not found`);
  if (!res.ok) throw new Error(`cancel failed: ${res.status}`);
}

/** URL превью ассета relative → /asset/<id>. */
export function assetUrl(assetId: string): string {
  return `/asset/${encodeURIComponent(assetId)}`;
}