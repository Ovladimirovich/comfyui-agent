/**
 * Тесты чистых функций UI-2 (без DOM/браузера), запускаются через `node --test`.
 * Проверяют только транспортные/хелапер-функции; НЕ вычисляют состояние агента.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { newSessionId, readSession } from "../session.ts";
import { eventsUrl, parseSSEEvent, initialFromSnapshot, hasRunningJob, messagesFromSnapshot } from "../sse.ts";
import { assetUrl } from "../api.ts";
import type { SessionSnapshot } from "../types.ts";

test("newSessionId генерирует непустую строку", () => {
  const id = newSessionId();
  assert.ok(typeof id === "string");
  assert.ok(id.length > 4);
});

test("readSession возвращает существующий session_id", () => {
  const store = {
    _v: new Map<string, string>(),
    getItem(k: string) { return this._v.get(k) ?? null; },
    setItem(k: string, v: string) { this._v.set(k, v); },
  };
  store.setItem("agent_ui_session_id", "abc123");
  assert.equal(readSession(store), "abc123");
});

test("readSession создаёт и сохраняет новый session_id при отсутствии", () => {
  const store = {
    _v: new Map<string, string>(),
    getItem(k: string) { return this._v.get(k) ?? null; },
    setItem(k: string, v: string) { this._v.set(k, v); },
  };
  const id = readSession(store);
  assert.ok(id);
  assert.equal(store._v.get("agent_ui_session_id"), id);
});

test("eventsUrl кодирует session_id", () => {
  assert.equal(eventsUrl("a b&c"), "/events?session_id=a%20b%26c");
});

test("parseSSEEvent парсит payload", () => {
  const ev = parseSSEEvent('{"type":"result","state":"SUCCESS"}');
  assert.equal(ev.type, "result");
  assert.equal(ev.state, "SUCCESS");
});

test("initialFromSnapshot извлекает dialog_state/active_*", () => {
  const snap: SessionSnapshot = {
    dialog_state: "running",
    active_asset: "asset-1",
    active_job: "job-1",
  };
  const s = initialFromSnapshot(snap);
  assert.equal(s.dialogState, "running");
  assert.equal(s.activeAsset, "asset-1");
  assert.equal(s.activeJob, "job-1");
});

test("hasRunningJob true при наличии active_job", () => {
  assert.equal(hasRunningJob({ active_job: "j1" } as SessionSnapshot), true);
  assert.equal(hasRunningJob({} as SessionSnapshot), false);
});

test("assetUrl строит корректный relative-путь", () => {
  assert.equal(assetUrl("img1"), "/asset/img1");
});

// --- UI-3: recovery (snapshot → сообщения чата) ---

test("messagesFromSnapshot: успешный ход → user + agent SUCCESS", () => {
  const snap: SessionSnapshot = {
    messages: [
      {
        turn: "сделай кота",
        capability: "image.generate",
        workflow: "txt2img@1.0.0",
        job: "job-1",
        outputs: ["asset-1"],
      },
    ],
  };
  const msgs = messagesFromSnapshot(snap);
  assert.equal(msgs.length, 2);
  assert.equal(msgs[0].role, "user");
  assert.equal(msgs[0].text, "сделай кота");
  assert.equal(msgs[0].state, "SUCCESS");
  assert.equal(msgs[1].role, "agent");
  assert.deepEqual(msgs[1].assets, ["asset-1"]);
});

test("messagesFromSnapshot: decision_failed → ошибка с причиной", () => {
  const snap: SessionSnapshot = {
    messages: [{ type: "decision_failed", reason: "модель не найдена", job: "job-x" }],
  };
  const msgs = messagesFromSnapshot(snap);
  assert.equal(msgs.length, 1);
  assert.equal(msgs[0].role, "error");
  assert.equal(msgs[0].state, "FAILED");
  assert.ok(msgs[0].error!.includes("модель не найдена"));
});

test("messagesFromSnapshot: dialog_state=error → unresolved в FAILED-сообщение", () => {
  const snap: SessionSnapshot = {
    dialog_state: "error",
    unresolved: [{ turn: "видео", error: "нет workflow с необходимой совместимостью" }],
  };
  const msgs = messagesFromSnapshot(snap);
  assert.equal(msgs.length, 1);
  assert.equal(msgs[0].role, "error");
  assert.equal(msgs[0].state, "FAILED");
});