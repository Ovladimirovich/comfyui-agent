/**
 * Agent UI — Shell (F2).
 *
 * Реальный сценарий: запрос → POST /api/chat → ConversationAgent.turn
 * → ExecutionPlan → execution backend → Job lifecycle → результат.
 *
 * Shell: навигация между зонами (hash-based, без react-router), глобальное
 * состояние сессии (session/dialog_state/connection/runtime), композиция зон.
 * Frontend — только кэш отображения: состояния приходят с backend через
 * существующие SSE-контракты (start/status/progress/chain_step/result/error)
 * и §21 API (/api/chat, /api/session, /api/jobs/{id}, /api/runtime, /asset/<id>).
 * Никакой локальной state machine агента здесь нет.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { capabilities, cancelJob, jobStatus, runtime, sendChat, sessionSnapshot, uploadAsset } from "./lib/api";
import { makeId } from "./lib/format";
import { readSession } from "./lib/session";
import { eventsUrl, messagesFromSnapshot, parseSSEEvent } from "./lib/sse";
import type { ConnectionState, JobStatus, RuntimeInfo, SessionSnapshot, SSEMessage, TurnMessage } from "./lib/types";
import { getZone, zoneFromHash, type ZoneId } from "./zones";
import EmptyState from "./components/common/EmptyState";
import ConversationZone from "./components/Conversation/ConversationZone";
import Sidebar from "./components/Shell/Sidebar";
import StatusBar from "./components/Shell/StatusBar";
import ZoneHeader from "./components/Shell/ZoneHeader";
import SystemZone from "./components/System/SystemZone";
import TaskPlanZone from "./components/Task/TaskPlanZone";
import ExecutionZone from "./components/Execution/ExecutionZone";
import ResultsZone from "./components/Results/ResultsZone";
import type { ChainStep } from "./components/Task/PlanSteps";

export default function App() {
  const [sessionId] = useState<string>(() => readSession(localStorage));
  const [activeZone, setActiveZone] = useState<ZoneId>(() => zoneFromHash(window.location.hash));
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<TurnMessage[]>([]);
  const [activeTurnId, setActiveTurnId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [dialogState, setDialogState] = useState<string | null>(null);
  const [caps, setCaps] = useState<string[]>([]);
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [runtimeInfo, setRuntimeInfo] = useState<RuntimeInfo | null>(null);
  const [snapshot, setSnapshot] = useState<SessionSnapshot | null>(null);
  // F3: Task & Plan state
  const [chainSteps, setChainSteps] = useState<ChainStep[]>([]);
  const [activeStepIndex, setActiveStepIndex] = useState<number>(-1);
  const [progressPct, setProgressPct] = useState<number | null>(null);
  const [userIntent, setUserIntent] = useState<string | null>(null);
  const [agentMessage, setAgentMessage] = useState<string | null>(null);
  // S9: вложение (один файл на turn, media-agnostic upload через /api/assets)
  const [attachFile, setAttachFile] = useState<File | null>(null);
  const attachFileRef = useRef<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const busy = sending || activeTurnId !== null;
  const hasActiveJob = messages.some((m) => m.jobId && (m.state === "RUNNING" || m.state === "QUEUED"));

  // ref для активного turn внутри SSE-хендлера (избегаем stale closure)
  const activeTurnIdRef = useRef<string | null>(null);
  useEffect(() => {
    activeTurnIdRef.current = activeTurnId;
  }, [activeTurnId]);

  const patchTurn = useCallback((id: string | null, patch: Partial<TurnMessage>) => {
    setMessages((prev) => (id ? prev.map((m) => (m.id === id ? { ...m, ...patch } : m)) : prev));
  }, []);

  // JOB метаданные: workflow/duration/error из GET /api/jobs/{id}
  const attachJob = useCallback(
    (turnId: string | null, jobId: string | null) => {
      if (!jobId || !turnId) return;
      jobStatus(jobId)
        .then((j: JobStatus) => {
          patchTurn(turnId, {
            jobId: j.prompt_id,
            state: j.state,
            workflow: j.workflow_id ? `${j.workflow_id}@${j.workflow_version}` : undefined,
            duration: j.duration || undefined,
            error: j.error,
            assets: j.output_assets?.length ? j.output_assets : undefined,
            runtimeGraph: j.runtime_graph ?? null,
          });
        })
        .catch(() => {});
    },
    [patchTurn]
  );

  // Навигация: hash-based (ROADMAP D.3, без react-router). UI-локальное состояние.
  useEffect(() => {
    const onHash = () => setActiveZone(zoneFromHash(window.location.hash));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const selectZone = useCallback((zone: ZoneId) => {
    window.location.hash = `/${zone}`;
    setActiveZone(zone);
  }, []);

  // Recovery после reload: /api/session snapshot (backend = source of truth)
  // + capabilities + runtime (F1 §21, fail-open).
  useEffect(() => {
    sessionSnapshot(sessionId)
      .then((snap) => {
        setSnapshot(snap as SessionSnapshot);
        setDialogState((snap.dialog_state as string) ?? null);
        const restored = messagesFromSnapshot(snap as never).map((r) => ({
          ...r,
          id: makeId(),
          progress: null,
        }));
        setMessages(restored);
        // F3: восстановить intent из последнего пользовательского сообщения
        const lastUserMsg = [...restored].reverse().find((m) => m.role === "user");
        if (lastUserMsg) setUserIntent(lastUserMsg.text);
      })
      .catch(() =>
        setMessages((prev) => [
          ...prev,
          { id: makeId(), role: "error", text: "Не удалось получить snapshot сессии", state: "FAILED", jobId: null, error: null, assets: [], progress: null },
        ])
      );
    capabilities()
      .then((c) => Array.isArray(c) && setCaps(c))
      .catch(() => {});
    runtime()
      .then((r) => setRuntimeInfo(r))
      .catch(() => {});
  }, [sessionId]);

  // Подписка на SSE-события существующих контрактов backend
  useEffect(() => {
    const es = new EventSource(eventsUrl(sessionId));
    setConnection("connecting");
    es.onopen = () => setConnection("open");
    es.onerror = () => setConnection("error");
    const handler = (e: MessageEvent) => {
      const ev = parseSSEEvent(e.data) as SSEMessage;
      switch (ev.type) {
        case "start":
          setDialogState("planning");
          // F3: сбросить plan state для нового turn
          setChainSteps([]);
          setActiveStepIndex(-1);
          setProgressPct(null);
          break;
        case "status":
          setDialogState(String(ev.state));
          break;
        case "progress":
          setDialogState("executing");
          setProgressPct(Number(ev.pct) ?? null);
          patchTurn(activeTurnIdRef.current, { state: "RUNNING", progress: Number(ev.pct) ?? null });
          break;
        case "chain_step": {
          setDialogState("chain");
          const cs = ev as { type: "chain_step"; step: number; total_steps: number; state: string; capability?: string; outputs?: string[] };
          setActiveStepIndex(cs.step);
          // Обновить/добавить шаг в цепочку
          setChainSteps((prev) => {
            const exists = prev.find((s) => s.step === cs.step);
            if (exists) {
              return prev.map((s) => (s.step === cs.step ? { ...s, state: cs.state as ChainStep["state"], capability: cs.capability ?? s.capability, outputs: cs.outputs ?? s.outputs } : s));
            }
            return [...prev, {
              step: cs.step,
              total_steps: cs.total_steps,
              state: (cs.state || "pending") as ChainStep["state"],
              capability: cs.capability || "",
              outputs: cs.outputs || [],
            }];
          });
          patchTurn(activeTurnIdRef.current, { state: "RUNNING" });
          break;
        }
        case "result": {
          const r = ev as never as {
            state?: string | null;
            active_job?: string | null;
            job?: string | null;
            assets?: string[];
            error?: string | null;
            dialog_state?: string;
            agent_message?: string;
          };
          const finalState = r.state ?? "SUCCESS";
          const jobId = r.job ?? r.active_job ?? null;
          patchTurn(activeTurnIdRef.current, {
            state: finalState,
            jobId,
            error: r.error ?? null,
            assets: r.assets ?? [],
          });
          setDialogState(finalState);
          // D-1A: agent_message из terminal event
          if (r.agent_message) {
            setAgentMessage(r.agent_message);
          }
          attachJob(activeTurnIdRef.current, jobId);
          setActiveTurnId(null);
          break;
        }
        case "error": {
          const err = String(ev.error ?? "неизвестная ошибка");
          patchTurn(activeTurnIdRef.current, { state: "FAILED", error: err });
          setMessages((prev) => [
            ...prev,
            { id: makeId(), role: "error", text: `Ошибка: ${err}`, state: "FAILED", jobId: null, error: err, assets: [], progress: null },
          ]);
          setDialogState("error");
          setActiveTurnId(null);
          break;
        }
        default:
          break;
      }
    };
    ["start", "status", "progress", "chain_step", "result", "error"].forEach((name) =>
      es.addEventListener(name, handler as EventListener)
    );
    return () => {
      es.close();
      setConnection("closed");
    };
  }, [sessionId, patchTurn, attachJob]);

  const submit = useCallback(async () => {
    const text = input.trim();
    if (!text || busy) return;
    const turnId = makeId();
    setInput("");
    setUserIntent(text); // F3: сохранить intent
    setMessages((prev) => [...prev, { id: turnId, role: "user", text, state: "QUEUED", jobId: null, error: null, assets: [], progress: null }]);
    setActiveTurnId(turnId);
    setSending(true);
    const file = attachFileRef.current;
    try {
      let assets: Record<string, unknown> | undefined;
      if (file) {
        // S9: загрузка вложения → assets[image].asset_id в /api/chat (AD-23 explicit input)
        const { asset_id } = await uploadAsset(file);
        assets = { image: { asset_id } };
      }
      await sendChat(sessionId, text, assets);
    } catch (err) {
      patchTurn(turnId, { state: "FAILED", error: String(err) });
      setMessages((prev) => [...prev, { id: makeId(), role: "error", text: `Ошибка отправки: ${String(err)}`, state: "FAILED", jobId: null, error: String(err), assets: [], progress: null }]);
      setDialogState("error");
      setActiveTurnId(null);
    } finally {
      setSending(false);
      // вложение однократное — сбрасываем после отправки
      attachFileRef.current = null;
      setAttachFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }, [input, busy, sessionId, patchTurn]);

  const cancelActive = useCallback(async () => {
    const last = messages[messages.length - 1];
    if (!last || !last.jobId) return;
    try {
      await cancelJob(last.jobId);
      patchTurn(last.id, { state: "CANCELLED" });
    } catch {
      // cancel живой задачи не реализован (D-5A); состояние всё равно придёт из /api/jobs
    }
  }, [messages, patchTurn]);

  const clearAttachment = useCallback(() => {
    attachFileRef.current = null;
    setAttachFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  const zone = getZone(activeZone);

  return (
    <div className="shell">
      <Sidebar active={activeZone} caps={caps} onSelect={selectZone} />
      <main className="shell__main">
        <ZoneHeader zone={zone} />
        <section className="shell__content">
          {zone.id === "conversation" && (
            <ConversationZone
              messages={messages}
              busy={busy}
              dialogState={dialogState}
              input={input}
              attachFile={attachFile}
              hasActiveJob={hasActiveJob}
              fileInputRef={fileInputRef}
              onInput={setInput}
              onAttach={(f) => {
                attachFileRef.current = f;
                setAttachFile(f);
              }}
              onClearAttachment={clearAttachment}
              onSubmit={() => void submit()}
              onCancelJob={() => void cancelActive()}
            />
          )}
          {zone.id === "task-plan" && (
            <TaskPlanZone
              userIntent={userIntent}
              dialogState={dialogState}
              steps={chainSteps}
              activeStepIndex={activeStepIndex}
              progressPct={progressPct}
              error={messages[messages.length - 1]?.error ?? null}
              jobId={messages[messages.length - 1]?.jobId ?? null}
              lastCapability={null} // TODO: из result event
              agentMessage={agentMessage}
            />
)}
            {zone.id === "execution" && (
              <ExecutionZone sessionId={sessionId} />
            )}
            {zone.id === "results" && (
              <ResultsZone
                assets={messages[messages.length - 1]?.assets ?? []}
                activeAsset={messages[messages.length - 1]?.assets?.[messages[messages.length - 1].assets.length - 1] ?? null}
                activeWorkflow={messages[messages.length - 1]?.workflow ?? null}
                jobId={messages[messages.length - 1]?.jobId ?? null}
                dialogState={dialogState}
                agentMessage={agentMessage}
                error={messages[messages.length - 1]?.error ?? null}
              />
            )}
            {zone.id === "system" && <SystemZone sessionId={sessionId} connection={connection} runtimeInfo={runtimeInfo} snapshot={snapshot} />}
            {zone.id !== "conversation" && zone.id !== "task-plan" && zone.id !== "execution" && zone.id !== "system" && <EmptyState title={zone.label} phase={zone.phase} body={zone.description} />}
        </section>
        <StatusBar sessionId={sessionId} connection={connection} runtimeInfo={runtimeInfo} />
      </main>
    </div>
  );
}