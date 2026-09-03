"""M15 Tests — Persistent Context + Session Recovery.

Тестирует:
- ContextPersistence: save, load, list_sessions, delete
- SessionManager: create, resume, list_sessions, save, delete
- Integration: ConversationAgent с session_manager
"""
from __future__ import annotations

import os
import tempfile
from typing import Optional

import pytest

from app.context.persistence import ContextPersistence
from app.context.session_manager import SessionManager
from app.conversation import ConversationContext


# --- ContextPersistence tests ---

class TestContextPersistence:
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = ContextPersistence(sessions_dir=tmpdir)
            ctx_dict = {
                "session_id": "test-session",
                "messages": [{"turn": "hello"}],
                "assets": ["asset1"],
                "jobs": ["job1"],
                "workflows": ["wf1@1.0"],
                "parameters": {"prompt": "a cat"},
                "active_task": "image.generate",
                "active_workflow": "wf1@1.0",
                "active_job": "job1",
                "active_asset": "asset1",
                "unresolved": [],
                "dialog_state": "idle",
            }
            persistence.save("test-session", ctx_dict)
            loaded = persistence.load("test-session")
            assert loaded is not None
            assert loaded["session_id"] == "test-session"
            assert loaded["messages"] == [{"turn": "hello"}]
            assert loaded["assets"] == ["asset1"]
            assert loaded["active_task"] == "image.generate"

    def test_load_nonexistent_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = ContextPersistence(sessions_dir=tmpdir)
            assert persistence.load("nonexistent") is None

    def test_multiple_snapshots_returns_last(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = ContextPersistence(sessions_dir=tmpdir)
            persistence.save("s1", {"session_id": "s1", "messages": [{"turn": "1"}]})
            persistence.save("s1", {"session_id": "s1", "messages": [{"turn": "1"}, {"turn": "2"}]})
            loaded = persistence.load("s1")
            assert len(loaded["messages"]) == 2

    def test_list_sessions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = ContextPersistence(sessions_dir=tmpdir)
            persistence.save("s1", {
                "session_id": "s1",
                "messages": [],
                "assets": ["a1"],
                "dialog_state": "idle",
                "active_task": None,
                "active_asset": None,
            })
            persistence.save("s2", {
                "session_id": "s2",
                "messages": [{"turn": "hi"}],
                "assets": [],
                "dialog_state": "working",
                "active_task": "image.generate",
                "active_asset": "a2",
            })
            sessions = persistence.list_sessions()
            assert len(sessions) == 2
            assert sessions[0]["session_id"] == "s1"
            assert sessions[1]["session_id"] == "s2"
            assert sessions[0]["messages_count"] == 0
            assert sessions[1]["messages_count"] == 1

    def test_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = ContextPersistence(sessions_dir=tmpdir)
            persistence.save("s1", {"session_id": "s1"})
            assert persistence.delete("s1") is True
            assert persistence.load("s1") is None
            assert persistence.delete("s1") is False

    def test_session_id_with_special_chars(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = ContextPersistence(sessions_dir=tmpdir)
            persistence.save("user/123\\test", {"session_id": "user/123\\test"})
            loaded = persistence.load("user/123\\test")
            assert loaded is not None


# --- SessionManager tests ---

class TestSessionManager:
    def test_create_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = ContextPersistence(sessions_dir=tmpdir)
            manager = SessionManager(persistence=persistence)
            sid = manager.create("my-session")
            assert sid == "my-session"
            sessions = manager.list_sessions()
            assert len(sessions) == 1
            assert sessions[0]["session_id"] == "my-session"

    def test_create_auto_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = ContextPersistence(sessions_dir=tmpdir)
            manager = SessionManager(persistence=persistence)
            sid = manager.create()
            assert sid is not None
            assert len(sid) > 0

    def test_resume_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = ContextPersistence(sessions_dir=tmpdir)
            manager = SessionManager(persistence=persistence)
            manager.create("s1")
            ctx = manager.resume("s1")
            assert ctx is not None
            assert ctx.session_id == "s1"
            assert ctx.dialog_state == "idle"

    def test_resume_nonexistent_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = ContextPersistence(sessions_dir=tmpdir)
            manager = SessionManager(persistence=persistence)
            assert manager.resume("nonexistent") is None

    def test_save_and_resume_preserves_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = ContextPersistence(sessions_dir=tmpdir)
            manager = SessionManager(persistence=persistence)
            sid = manager.create("s1")
            ctx = manager.resume(sid)
            ctx.messages.append({"turn": "hello"})
            ctx.active_task = "image.generate"
            ctx.assets.add("a1")
            manager.save(sid, ctx)
            # Resume и проверяем состояние
            ctx2 = manager.resume(sid)
            assert ctx2.messages == [{"turn": "hello"}]
            assert ctx2.active_task == "image.generate"
            assert ctx2.assets == {"a1"}

    def test_list_sessions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = ContextPersistence(sessions_dir=tmpdir)
            manager = SessionManager(persistence=persistence)
            manager.create("s1")
            manager.create("s2")
            sessions = manager.list_sessions()
            assert len(sessions) == 2

    def test_delete_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = ContextPersistence(sessions_dir=tmpdir)
            manager = SessionManager(persistence=persistence)
            manager.create("s1")
            assert manager.delete("s1") is True
            assert manager.resume("s1") is None

    def test_session_isolation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = ContextPersistence(sessions_dir=tmpdir)
            manager = SessionManager(persistence=persistence)
            manager.create("s1")
            manager.create("s2")
            ctx1 = manager.resume("s1")
            ctx1.messages.append({"turn": "hello from s1"})
            manager.save("s1", ctx1)
            # s2 не должен содержать сообщения из s1
            ctx2 = manager.resume("s2")
            assert ctx2.messages == []
