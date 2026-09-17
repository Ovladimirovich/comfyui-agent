/**
 * Реестр зон Operator UI (ROADMAP §E Navigation / Information Architecture).
 * ui.phase = фаза roadmap, реализующая зону; null = зона реализована.
 * Правило §E: зона с пустым/неподдерживаемым backend скрывается (без фейков).
 */

export interface ZoneDef {
  id: string;
  label: string;
  description: string;
  phase: string | null;
}

export const ZONES: readonly ZoneDef[] = [
  {
    id: "conversation",
    label: "Conversation",
    description: "чат, вложения, dialog_state",
    phase: null,
  },
  {
    id: "task-plan",
    label: "Task & Plan",
    description: "intent, constraints, план/chain",
    phase: "F3",
  },
  {
    id: "execution",
    label: "Execution",
    description: "job state, progress, cancel, ComfyUI-link",
    phase: "F4",
  },
  {
    id: "results",
    label: "Results & Assets",
    description: "preview, lineage, verification",
    phase: "F5",
  },
  {
    id: "history",
    label: "History",
    description: "список задач, chain summary, повторный запуск",
    phase: "F6 (требует D-2)",
  },
  {
    id: "knowledge",
    label: "Knowledge",
    description: "node explain/search, gaps, self-test",
    phase: "F8",
  },
  {
    id: "workflows",
    label: "Workflows",
    description: "список/детали, provenance",
    phase: "F8",
  },
  {
    id: "discovery",
    label: "Discovery",
    description: "candidates от M29 (register/execute — по approval)",
    phase: "F8",
  },
  {
    id: "system",
    label: "System",
    description: "session, connection, runtime",
    phase: null,
  },
];

export type ZoneId = (typeof ZONES)[number]["id"];

export const DEFAULT_ZONE: ZoneId = "conversation";

export function getZone(id: string): ZoneDef {
  return ZONES.find((z) => z.id === id) ?? ZONES[0];
}

/** Навигация hash-based (без react-router, ROADMAP D.3): "#/conversation" → zone. */
export function zoneFromHash(hash: string): ZoneId {
  const raw = hash.replace(/^#\/?/, "").trim();
  // Убираем query параметры и fragment
  const id = raw.split(/[?#]/)[0];
  return ZONES.some((z) => z.id === id) ? (id as ZoneId) : DEFAULT_ZONE;
}