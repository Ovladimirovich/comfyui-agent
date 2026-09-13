"""Concurrency tests — session isolation, concurrent writes/reads, race conditions.

Все тесты используют mocks/seeds, не требуют реального ComfyUI.
Проверяют Thread Safety без production changes.

Категории:
  1. Session isolation (parallel A/B sessions)
  2. Concurrent SessionStream writers
  3. Concurrent readers
  4. Session creation race
  5. Parallel independent sessions
  6. Concurrent job completion
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Optional

import pytest

from app.assets.store import AssetStore
from app.conversation import ConversationAgent, ConversationContext
from app.context.session_manager import SessionManager
from app.engine.history import ExecutionHistory, ExecutionRecord
from app.engine.job import Job, JobState
from app.ui import ComfyUIServer, SessionStream


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _make_store(tmp_path) -> AssetStore:
    return AssetStore(root=str(tmp_path / "assets"))


def _make_agent(tmp_path, **kwargs) -> ConversationAgent:
    store = _make_store(tmp_path)
    return ConversationAgent(store, **kwargs)


def _fake_job(
    prompt_id: str = "j1",
    workflow_id: str = "w1",
    version: str = "1",
    capability: str = "image.generate",
    state: JobState = JobState.SUCCESS,
    output_assets: list[str] | None = None,
) -> Job:
    return Job(
        prompt_id=prompt_id,
        workflow_id=workflow_id,
        version=version,
        capability=capability,
        state=state,
        output_assets=output_assets or [],
    )


# ─────────────────────────────────────────────────────────────
# Category 1: Session isolation (parallel A/B sessions)
# ─────────────────────────────────────────────────────────────

class TestSessionIsolation:
    """Параллельные сессии A и B не должны влиять друг на друга."""

    def test_different_session_ids_get_separate_contexts(self, tmp_path):
        agent = _make_agent(tmp_path)
        ctx_a = agent.session("session-A")
        ctx_b = agent.session("session-B")
        assert ctx_a is not ctx_b
        assert ctx_a.session_id == "session-A"
        assert ctx_b.session_id == "session-B"

    def test_same_session_id_returns_same_context(self, tmp_path):
        agent = _make_agent(tmp_path)
        ctx1 = agent.session("session-X")
        ctx2 = agent.session("session-X")
        assert ctx1 is ctx2

    def test_parallel_sessions_on_same_agent_isolated(
        self, tmp_path, session_a="sA", session_b="sB"
    ):
        """Два потока работают с разными сессиями через один Agent — контексты изолированы."""
        agent = _make_agent(tmp_path)
        barrier = threading.Barrier(2)
        results: dict[str, list] = {"a": [], "b": []}

        def work_session(sid: str, key: str):
            ctx = agent.session(sid)
            barrier.wait(timeout=5)
            # Модифицируем контекст из потока
            ctx.messages.append({"turn": f"{key}-msg"})
            ctx.assets.add(f"asset-{key}")
            results[key].append(ctx.messages[-1])

        t1 = threading.Thread(target=work_session, args=(session_a, "a"))
        t2 = threading.Thread(target=work_session, args=(session_b, "b"))
        t1.start(); t2.start()
        t1.join(timeout=5); t2.join(timeout=5)

        assert len(results["a"]) == 1
        assert len(results["b"]) == 1
        # Контексты изолированы: в A只有 a-сообщения, в B只有 b-сообщения
        ctx_a = agent.session(session_a)
        ctx_b = agent.session(session_b)
        a_messages = [m for m in ctx_a.messages if "a-msg" in str(m)]
        b_messages = [m for m in ctx_a.messages if "b-msg" in str(m)]
        assert len(a_messages) == 1
        assert len(b_messages) == 0  # cross-contamination отсутствует

    def test_session_stream_isolation(self, tmp_path):
        """SessionStream для разных сессий не пересекаются."""
        server = ComfyUIServer(_make_store(tmp_path))
        s1 = server.stream("s1")
        s2 = server.stream("s2")
        assert s1 is not s2
        s1.push({"type": "start"})
        assert len(s1._events) == 1
        assert len(s2._events) == 0


# ─────────────────────────────────────────────────────────────
# Category 2: Concurrent SessionStream writers
# ─────────────────────────────────────────────────────────────

class TestConcurrentStreamWriters:
    """Несколько потоков одновременно пушат события в один SessionStream."""

    def test_all_events_arrive(self):
        """100 потоков пушат по 10 событий — все 100 должны попасть в _events."""
        stream = SessionStream()
        n_threads = 100
        events_per_thread = 10
        expected = n_threads * events_per_thread
        barrier = threading.Barrier(n_threads)

        def writer(thread_id: int):
            barrier.wait(timeout=5)
            for i in range(events_per_thread):
                stream.push({"thread": thread_id, "seq": i})

        threads = [threading.Thread(target=writer, args=(tid,)) for tid in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(stream._events) == expected

    def test_events_not_lost_under_contention(self):
        """64 потока пушают по 50 событий — ни одно не теряется."""
        stream = SessionStream()
        n = 64
        per = 50
        barrier = threading.Barrier(n)

        def writer(tid: int):
            barrier.wait(timeout=5)
            for i in range(per):
                stream.push({"id": f"{tid}-{i}"})

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(stream._events) == n * per
        # Проверяем уникальность (каждый event имеет уникальный id)
        ids = {e["id"] for e in stream._events}
        assert len(ids) == n * per

    def test_terminal_event_sets_done(self):
        """Terminal event (result/error) устанавливает _done=True即使 среди других пушей."""
        stream = SessionStream()
        n = 50
        barrier = threading.Barrier(n + 1)

        def writer(i: int):
            barrier.wait(timeout=5)
            stream.push({"type": "status", "n": i})

        def terminal_pusher():
            barrier.wait(timeout=5)
            stream.push({"type": "result", "ok": True})

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(n)]
        term = threading.Thread(target=terminal_pusher)
        threads.append(term)
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert stream._done is True
        terminal_events = [e for e in stream._events if e.get("type") in ("result", "error")]
        assert len(terminal_events) == 1


# ─────────────────────────────────────────────────────────────
# Category 3: Concurrent readers
# ─────────────────────────────────────────────────────────────

class TestConcurrentReaders:
    """Несколько потоков одновременно читают из SessionStream через wait_next."""

    def test_multiple_readers_get_same_event(self):
        """5 читателей ждут idx=0 — все получают одно и то же событие."""
        stream = SessionStream()
        n_readers = 5
        results: list[Optional[dict]] = [None] * n_readers
        barrier = threading.Barrier(n_readers)

        def reader(idx: int):
            barrier.wait(timeout=5)
            results[idx] = stream.wait_next(0, timeout=2)

        threads = [threading.Thread(target=reader, args=(i,)) for i in range(n_readers)]
        for t in threads:
            t.start()
        # Пушим событие после старта всех читателей
        time.sleep(0.05)
        stream.push({"type": "status", "n": 1})
        for t in threads:
            t.join(timeout=5)

        for i in range(n_readers):
            assert results[i] is not None, f"reader {i} got None"
            assert results[i]["type"] == "status"

    def test_sequential_readers_no_duplication(self):
        """Индексация через idx предотвращает дублирование при последовательном чтении."""
        stream = SessionStream()
        reader_events: dict[int, list] = {}
        lock = threading.Lock()

        def reader(reader_id: int):
            events = []
            idx = 0
            while True:
                ev = stream.wait_next(idx, timeout=0.5)
                if ev is None:
                    break
                events.append(ev)
                idx += 1
            with lock:
                reader_events[reader_id] = events

        threads = [threading.Thread(target=reader, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for i in range(5):
            stream.push({"seq": i})
        time.sleep(0.1)
        stream.push({"type": "result"})
        for t in threads:
            t.join(timeout=5)

        # Каждый reader получил ровно 6 событий (5 status + 1 result)
        for reader_id, events in reader_events.items():
            assert len(events) == 6, f"reader {reader_id} got {len(events)} events, expected 6"
            assert events[-1]["type"] == "result"

    def test_reader_timeout_returns_none(self):
        """wait_next с таймаутом без событий возвращает None, не блокирует поток."""
        stream = SessionStream()
        results: list = []

        def reader():
            r = stream.wait_next(0, timeout=0.1)
            results.append(r)

        t = threading.Thread(target=reader)
        t.start()
        t.join(timeout=1)
        assert len(results) == 1
        assert results[0] is None

    def test_writer_wakes_multiple_waiters(self):
        """push() с notify_all будит всех等待ающих читателей."""
        stream = SessionStream()
        n_waiters = 20
        results: list[Optional[dict]] = [None] * n_waiters
        barrier = threading.Barrier(n_waiters)

        def waiter(i: int):
            barrier.wait(timeout=5)
            results[i] = stream.wait_next(0, timeout=5)

        threads = [threading.Thread(target=waiter, args=(i,)) for i in range(n_waiters)]
        for t in threads:
            t.start()
        time.sleep(0.05)
        stream.push({"type": "wake"})
        for t in threads:
            t.join(timeout=5)

        for i in range(n_waiters):
            assert results[i] is not None, f"waiter {i} was not woken"
            assert results[i]["type"] == "wake"


# ─────────────────────────────────────────────────────────────
# Category 4: Session creation race
# ─────────────────────────────────────────────────────────────

class TestSessionCreationRace:
    """Несколько потоков одновременно запрашивают одну и ту же сессию — гонка за создание."""

    def test_session_creation_race_single_context(self, tmp_path):
        """100 потоков вызывают agent.session('X') одновременно — создастся только один ConversationContext."""
        agent = _make_agent(tmp_path)
        n = 100
        contexts: list[ConversationContext] = [None] * n  # type: ignore
        barrier = threading.Barrier(n)

        def create_session(i: int):
            barrier.wait(timeout=5)
            contexts[i] = agent.session("race-session")

        threads = [threading.Thread(target=create_session, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # Все потоки получили один и тот же объект (identity == equality)
        unique_ids = {id(ctx) for ctx in contexts}
        assert len(unique_ids) == 1, (
            f"Race created {len(unique_ids)} different contexts; "
            f"expected 1 (all same object). IDs: {unique_ids}"
        )
        # Все потоки видят одну сессию
        assert len(agent.sessions) == 1

    def test_concurrent_session_get_does_not_duplicate(self, tmp_path):
        """Параллельные get() + get() на отсутствующую сессию — дубликатов нет."""
        agent = _make_agent(tmp_path)
        results: list[ConversationContext] = []
        lock = threading.Lock()

        def get_session():
            ctx = agent.session("dup-check")
            with lock:
                results.append(ctx)

        threads = [threading.Thread(target=get_session) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        unique = {id(ctx) for ctx in results}
        assert len(unique) == 1
        assert len(agent.sessions) == 1

    def test_concurrent_session_create_different_ids(self, tmp_path):
        """Параллельное создание РАЗНЫХ сессий — ни одна не потеряется."""
        agent = _make_agent(tmp_path)
        n = 50
        lock = threading.Lock()
        created: dict[str, ConversationContext] = {}

        def create_one(i: int):
            ctx = agent.session(f"session-{i}")
            with lock:
                created[f"session-{i}"] = ctx

        threads = [threading.Thread(target=create_one, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(created) == n
        assert len(agent.sessions) == n
        # Каждый context — уникальный объект
        assert len({id(ctx) for ctx in created.values()}) == n


# ─────────────────────────────────────────────────────────────
# Category 5: Parallel independent sessions
# ─────────────────────────────────────────────────────────────

class TestParallelIndependentSessions:
    """Независимые сессии работают параллельно без взаимного влияния."""

    def test_parallel_session_stream_push_read(self, tmp_path):
        """Две сессии: push в A не попадает в B."""
        server = ComfyUIServer(_make_store(tmp_path))
        s1 = server.stream("s1")
        s2 = server.stream("s2")
        n = 200
        barrier = threading.Barrier(2)

        def pusher(stream: SessionStream, label: str):
            barrier.wait(timeout=5)
            for i in range(n):
                stream.push({"from": label, "i": i})

        t1 = threading.Thread(target=pusher, args=(s1, "s1"))
        t2 = threading.Thread(target=pusher, args=(s2, "s2"))
        t1.start(); t2.start()
        t1.join(timeout=10); t2.join(timeout=10)

        assert len(s1._events) == n
        assert len(s2._events) == n
        assert all(e["from"] == "s1" for e in s1._events)
        assert all(e["from"] == "s2" for e in s2._events)

    def test_parallel_agent_sessions_separate_state(self, tmp_path):
        """Параллельные сессии через ConversationAgent — модификации изолированы."""
        agent = _make_agent(tmp_path)
        n = 10
        barrier = threading.Barrier(n)
        results: dict[str, list] = {}
        lock = threading.Lock()

        def modify_session(sid: str):
            barrier.wait(timeout=5)
            ctx = agent.session(sid)
            ctx.messages.append({"sid": sid})
            ctx.assets.add(f"asset-{sid}")
            with lock:
                results[sid] = list(ctx.messages)

        threads = [threading.Thread(target=modify_session, args=(f"s{i}",)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        for sid in [f"s{i}" for i in range(n)]:
            msgs = results[sid]
            assert len(msgs) == 1
            assert msgs[0]["sid"] == sid
            # Другие сессии не contamination
            other_msgs = [m for m in msgs if m["sid"] != sid]
            assert len(other_msgs) == 0

    def test_independent_session_concurrent_asset_ingest(self, tmp_path):
        """Две сессии параллельно добавляют assets через один store — без потерь."""
        store = _make_store(tmp_path)
        n_per_session = 10
        barrier = threading.Barrier(2)
        lock = threading.Lock()
        session_assets: dict[str, list] = {"a": [], "b": []}

        def ingest_files(session_key: str, count: int):
            barrier.wait(timeout=5)
            for i in range(count):
                # Создаём фиктивный файл
                f = tmp_path / f"file_{session_key}_{i}.txt"
                f.write_text(f"content-{session_key}-{i}")
                asset = store.ingest(str(f), type="text", metadata={"session": session_key})
                with lock:
                    session_assets[session_key].append(asset.id)

        t1 = threading.Thread(target=ingest_files, args=("a", n_per_session))
        t2 = threading.Thread(target=ingest_files, args=("b", n_per_session))
        t1.start(); t2.start()
        t1.join(timeout=10); t2.join(timeout=10)

        assert len(session_assets["a"]) == n_per_session
        assert len(session_assets["b"]) == n_per_session
        # Asset IDs уникальны
        all_ids = set(session_assets["a"]) | set(session_assets["b"])
        assert len(all_ids) == 2 * n_per_session
        # Каждый asset принадлежит правильной сессии
        for aid in session_assets["a"]:
            assert store.get(aid).metadata["session"] == "a"


# ─────────────────────────────────────────────────────────────
# Category 6: Concurrent job completion
# ─────────────────────────────────────────────────────────────

class TestConcurrentJobCompletion:
    """Параллельные завершения задач (Job completion) через ExecutionHistory."""

    def test_concurrent_record_appends(self):
        """100 потоков записывают ExecutionRecord — ни одна запись не теряется."""
        history = ExecutionHistory()
        n = 100
        barrier = threading.Barrier(n)

        def record_job(i: int):
            barrier.wait(timeout=5)
            rec = ExecutionRecord(
                prompt_id=f"job-{i}",
                capability="image.generate",
                state="SUCCESS",
                duration=1.0 + i * 0.01,
            )
            history.record(rec)

        threads = [threading.Thread(target=record_job, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert history.count() == n

    def test_concurrent_record_and_read(self):
        """Один поток пишет, другой читает — без крашей."""
        history = ExecutionHistory()
        n = 50
        reader_started = threading.Event()
        read_results: list[int] = []

        def writer():
            for i in range(n):
                rec = ExecutionRecord(
                    prompt_id=f"w{i}",
                    capability="image.generate",
                    state="SUCCESS",
                )
                history.record(rec)

        def reader():
            reader_started.set()
            while history.count() < n:
                count = history.count()
                read_results.append(count)
                time.sleep(0.001)
            # Финальное чтение после завершения записи
            read_results.append(history.count())

        tw = threading.Thread(target=writer)
        tr = threading.Thread(target=reader)
        tr.start()
        reader_started.wait(timeout=1)
        tw.start()
        tw.join(timeout=10)
        tr.join(timeout=10)

        assert history.count() == n
        # Промежуточные чтения не привели к краху
        assert len(read_results) > 0

    def test_concurrent_terminal_events_multiple_sessions(self):
        """Две сессии параллельно получают terminal event — оба завершаются корректно."""
        n_sessions = 2
        streams = [SessionStream() for _ in range(n_sessions)]
        n_events_per = 50
        barrier = threading.Barrier(n_sessions)
        done_flags = [threading.Event() for _ in range(n_sessions)]

        def pusher(idx: int):
            barrier.wait(timeout=5)
            for i in range(n_events_per):
                streams[idx].push({"seq": i})
            streams[idx].push({"type": "result", "done": True})
            done_flags[idx].set()

        threads = [threading.Thread(target=pusher, args=(i,)) for i in range(n_sessions)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        for i in range(n_sessions):
            assert done_flags[i].is_set()
            assert streams[i]._done is True
            assert len(streams[i]._events) == n_events_per + 1

    def test_execution_history_concurrent_record_and_query(self):
        """Параллельно записываем и запрашиваем ExecutionHistory — без потерь."""
        history = ExecutionHistory()
        n = 100
        barrier = threading.Barrier(n)
        lock = threading.Lock()
        query_results: list[dict] = []

        def record_and_query(i: int):
            barrier.wait(timeout=5)
            rec = ExecutionRecord(
                prompt_id=f"rq{i}",
                capability="image.generate" if i % 2 == 0 else "video.generate",
                state="SUCCESS",
                duration=float(i),
            )
            history.record(rec)
            # Параллельный запрос
            attempts = history.get_attempts()
            with lock:
                query_results.append({"i": i, "count": len(attempts)})

        threads = [threading.Thread(target=record_and_query, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # Все записи на месте
        assert history.count() == n
        # Все запросы вернули результат (не упали)
        assert len(query_results) == n
        # Все count >= 1 (хотя бы текущая запись)
        for r in query_results:
            assert r["count"] >= 1
