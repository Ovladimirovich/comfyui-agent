/**
 * Agent UI — first vertical slice (UI-3, Conversation).
 *
 * Реальный сценарий: запрос → POST /api/chat → ConversationAgent.turn
 * → ExecutionPlan → execution backend → Job lifecycle → результат.
 *
 * Frontend — только кэш отображения: состояния приходят с backend через
 * существующие SSE-контракты (start/status/progress/chain_step/result/error)
 * и §21 API (/api/chat, /api/session, /api/jobs/{id}, /asset/<id>).
 * Никакой локальной state machine агента здесь нет.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { capabilities, cancelJob, jobStatus, sendChat, sessionSnapshot, assetUrl, uploadAsset } from "./lib/api";
import { eventsUrl, messagesFromSnapshot, parseSSEEvent } from "./lib/sse";
import { readSession } from "./lib/session";
import type { JobStatus, SSEMessage } from "./lib/types";

interface TurnMessage {
  id: string;
  role: "user" | "agent" | "system" | "error";
  text: string;
  state: string | null;
  jobId: string | null;
  error: string | null;
  assets: string[];
  progress: number | null;
  workflow?: string;
  duration?: number;
}

const STATE_COLOR: Record<string, string> = {
  QUEUED: "#d8a13c",
  RUNNING: "#2f6df0",
  SUCCESS: "#3cbf6f",
  FAILED: "#e5484d",
  CANCELLED: "#8a8f98",
  error: "#e5484d",
};

let nextId = 0;
function makeId(): string {
  nextId += 1;
  return `t${Date.now()}_${nextId}`;
}

function MessageBubble({ m }: { m: TurnMessage }) {
  const isUser = m.role === "user";
  const isError = m.role === "error" || m.state === "FAILED";
  return (
    <div
      style={{
        margin: "8px 0",
        display: "flex",
        flexDirection: "column",
        alignItems: isUser ? "flex-end" : "flex-start",
      }}
    >
      <div
        style={{
          maxWidth: "85%",
          padding: "6px 10px",
          borderRadius: 10,
          background: isUser ? "#1e3a5f" : isError ? "#3a1c1f" : "#1d2530",
          border: isError ? "1px solid #e5484d" : "1px solid transparent",
          whiteSpace: "pre-wrap",
        }}
      >
        {m.text}
      </div>
      {m.state && (
        <div style={{ fontSize: 11, opacity: 0.75, color: isError ? "#e5484d" : "#8aa0b6", marginTop: 2 }}>
          <span style={{ color: STATE_COLOR[m.state] ?? "#8aa0b6" }}>{m.state}</span>
          {m.workflow ? ` · ${m.workflow}` : ""}
          {typeof m.duration === "number" ? ` · ${m.duration.toFixed(1)}s` : ""}
          {m.jobId ? ` · job ${m.jobId.slice(0, 12)}…` : ""}
          {m.progress != null ? ` · ${m.progress}%` : ""}
        </div>
      )}
      {m.progress != null && m.state === "RUNNING" && (
        <div style={{ width: "85%", height: 5, marginTop: 3, background: "#1a1e27", borderRadius: 3, overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${m.progress}%`, background: "#2f6df0", transition: "width 0.3s ease" }} />
        </div>
      )}
      {m.error && m.state === "FAILED" && (
        <div style={{ fontSize: 12, color: "#e5484d", marginTop: 2 }}>Ошибка: {m.error}</div>
      )}
      {m.assets.length > 0 && (
        <div style={{ marginTop: 6, display: "flex", flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
          {m.assets.map((aid) => (
            <AssetCard key={aid} assetId={aid} initialText={m.text} />
          ))}
        </div>
      )}
    </div>
  );
}

/** Медиа-агностичный показ ассета: image → preview; иначе — карточка со ссылкой. */
function AssetCard({ assetId, initialText }: { assetId: string; initialText: string }) {
  const [broken, setBroken] = useState(false);
  const url = assetUrl(assetId);
  if (broken) {
    return (
      <a href={url} download style={{ display: "block", padding: 6, border: "1px solid #2a2f3a", borderRadius: 8, background: "#11151c", color: "#8aa0b6", fontSize: 12 }}>
        {assetId.slice(0, 18)}… ({initialText.includes("video") || initialText.includes("audio") ? "не-изображение" : "файл"}) — скачать
      </a>
    );
  }
  return (
    <div style={{ border: "1px solid #2a2f3a", borderRadius: 8, padding: 4, background: "#11151c" }}>
      <img
        src={url}
        alt={assetId}
        style={{ maxWidth: 180, maxHeight: 140, display: "block", borderRadius: 4 }}
        onError={() => setBroken(true)}
      />
    </div>
  );
}

export default function App() {
  const [sessionId] = useState<string>(() => readSession(localStorage));
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<TurnMessage[]>([]);
  const [activeTurnId, setActiveTurnId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [dialogState, setDialogState] = useState<string | null>(null);
  const [caps, setCaps] = useState<string[]>([]);
  const listRef = useRef<HTMLDivElement | null>(null);
  // S9: вложение (один файл на turn, media-agnostic upload через /api/assets)
  const [attachFile, setAttachFile] = useState<File | null>(null);
  const attachFileRef = useRef<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const busy = sending || activeTurnId !== null;

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
          });
        })
        .catch(() => {});
    },
    [patchTurn]
  );

  // Recovery после reload: /api/session snapshot (backend = source of truth)
  useEffect(() => {
    sessionSnapshot(sessionId)
      .then((snap) => {
        setDialogState((snap.dialog_state as string) ?? null);
        const restored = messagesFromSnapshot(snap as never).map((r) => ({
          ...r,
          id: makeId(),
          progress: null,
        }));
        setMessages(restored);
      })
      .catch(() => setMessages((prev) => [...prev, { id: makeId(), role: "error", text: "Не удалось получить snapshot сессии", state: "FAILED", jobId: null, error: null, assets: [], progress: null }]));
    capabilities()
      .then((c) => Array.isArray(c) && setCaps(c))
      .catch(() => {});
  }, [sessionId]);

  // Подписка на SSE-события существующих контрактов backend
  useEffect(() => {
    const es = new EventSource(eventsUrl(sessionId));
    const handler = (e: MessageEvent) => {
      const ev = parseSSEEvent(e.data) as SSEMessage;
      switch (ev.type) {
        case "start":
          setDialogState("planning");
          break;
        case "status":
          setDialogState(String(ev.state));
          break;
        case "progress":
          setDialogState("executing");
          patchTurn(activeTurnIdRef.current, { state: "RUNNING", progress: Number(ev.pct) ?? null });
          break;
        case "chain_step":
          setDialogState("chain");
          patchTurn(activeTurnIdRef.current, { state: "RUNNING" });
          break;
        case "result": {
          const r = ev as never as {
            state?: string | null;
            active_job?: string | null;
            job?: string | null;
            assets?: string[];
            error?: string | null;
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
    return () => es.close();
  }, [sessionId, patchTurn, attachJob]);

  // ref для активного turn внутри SSE-хендлера (избегаем stale closure)
  const activeTurnIdRef = useRef<string | null>(null);
  useEffect(() => {
    activeTurnIdRef.current = activeTurnId;
  }, [activeTurnId]);

  // Автоскролл к последнему сообщению
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, dialogState]);

  const submit = useCallback(async () => {
    const text = input.trim();
    if (!text || busy) return;
    const turnId = makeId();
    setInput("");
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

  return (
    <div style={{ padding: 16, fontFamily: "system-ui, sans-serif", background: "#0f1115", color: "#e6e6e6" }}>
      <header style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <b>ComfyUI Agent UI</b>
        <span style={{ opacity: 0.7 }}>Operator UI · UI-3 vertical slice</span>
        <span style={{ marginLeft: "auto", opacity: 0.7 }}>session: {sessionId.slice(0, 10)}…</span>
        <span style={{ opacity: 0.7 }}>state: {dialogState ?? "—"}</span>
      </header>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 260px", gap: 16, marginTop: 16 }}>
        <section>
          <div
            ref={listRef}
            style={{
              minHeight: 360,
              maxHeight: "62vh",
              overflowY: "auto",
              border: "1px solid #2a2f3a",
              borderRadius: 8,
              padding: 10,
              background: "#11151c",
            }}
          >
            {messages.length === 0 && <span style={{ opacity: 0.5 }}>Введите запрос ниже. Агент выполнит его через Agent Core и покажет результат.</span>}
            {messages.map((m) => (
              <MessageBubble key={m.id} m={m} />
            ))}
            {busy && (
              <div style={{ fontSize: 12, opacity: 0.7, color: "#8aa0b6" }}>
                <span style={{ color: STATE_COLOR.RUNNING }}>RUNNING</span> — выполняется…
              </div>
            )}
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <label
              style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #2a2f3a", background: "#11151c", color: attachFile ? "#8aa0b6" : "#8aa0b6", cursor: busy ? "default" : "pointer", display: "flex", alignItems: "center", fontSize: 13 }}
              title="Прикрепить изображение"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                hidden
                disabled={busy}
                onChange={(e) => {
                  const f = e.target.files?.[0] ?? null;
                  attachFileRef.current = f;
                  setAttachFile(f);
                }}
              />
              {attachFile ? "📎 " + attachFile.name : "📎 Прикрепить"}
            </label>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={attachFile ? "Опишите, что сделать с этим изображением…" : "Например: сгенерируй фото кота"}
              disabled={busy}
              style={{ flex: 1, padding: 8, borderRadius: 8, border: "1px solid #2a2f3a", background: "#0c0f14", color: "#e6e6e6" }}
              onKeyDown={(e) => {
                if (e.key === "Enter") void submit();
              }}
            />
            <button onClick={submit} disabled={busy || !input.trim()} style={{ padding: "8px 16px", borderRadius: 8, border: "none", background: busy ? "#3a4a6a" : "#2f6df0", color: "#fff", cursor: busy ? "default" : "pointer" }}>
              {busy ? "Выполняется…" : "Отправить"}
            </button>
          </div>
          {attachFile && (
            <div style={{ display: "flex", gap: 8, marginTop: 6, fontSize: 12, alignItems: "center" }}>
              <img src={URL.createObjectURL(attachFile)} alt="" style={{ maxWidth: 56, maxHeight: 40, borderRadius: 4, border: "1px solid #2a2f3a" }} />
              <span style={{ opacity: 0.75 }}>изображение будет использовано как вход (image.edit)</span>
              <button
                onClick={() => {
                  attachFileRef.current = null;
                  setAttachFile(null);
                  if (fileInputRef.current) fileInputRef.current.value = "";
                }}
                style={{ marginLeft: 4, padding: "2px 8px", fontSize: 12, background: "#1d2530", color: "#e5484d", border: "1px solid #e5484d", borderRadius: 6, cursor: "pointer" }}
              >
                Убрать
              </button>
            </div>
          )}
        </section>
        <aside style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ border: "1px solid #2a2f3a", borderRadius: 8, padding: 10, background: "#11151c" }}>
            <h4 style={{ margin: "0 0 6px" }}>Capabilities</h4>
            {caps.length === 0 ? <span style={{ opacity: 0.6, fontSize: 12 }}>недоступны</span> : <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12 }}>{caps.map((c) => <li key={c}>{c}</li>)}</ul>}
          </div>
          <div style={{ border: "1px solid #2a2f3a", borderRadius: 8, padding: 10, background: "#11151c" }}>
            <h4 style={{ margin: "0 0 6px" }}>Job lifecycle</h4>
            <div style={{ fontSize: 12, display: "flex", flexDirection: "column", gap: 4 }}>
              {(["QUEUED", "RUNNING", "SUCCESS", "FAILED", "CANCELLED"] as const).map((s) => (
                <span key={s}>
                  <span style={{ color: STATE_COLOR[s] }}>●</span> {s}
                </span>
              ))}
            </div>
            {messages.some((m) => m.jobId && (m.state === "RUNNING" || m.state === "QUEUED")) && (
              <button onClick={cancelActive} style={{ marginTop: 8, padding: "6px 10px", fontSize: 12, background: "#3a1c1f", color: "#e5484d", border: "1px solid #e5484d", borderRadius: 6 }}>
                Отменить задачу (best-effort)
              </button>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}