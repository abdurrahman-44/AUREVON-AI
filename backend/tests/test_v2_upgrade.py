import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.api.routes import chat as chat_routes
from backend.app.core.config import settings
from backend.app.core.logging import error_tracker
from backend.app.core.rate_limit import rate_limiter
from backend.app.core.security import create_access_token, hash_password
from backend.app.database.session import Base, _apply_v2_column_upgrades, get_db
from backend.app.main import app
from backend.app.models.entities import AIRequestLog, Conversation, Document, Memory, User
from backend.app.repositories.user_repo import UserRepository
from backend.app.services.ai.base import BaseAIProvider
from backend.scripts import bootstrap_owner as cli_bootstrap


async def _make_isolated_db(tmp_path: Path, name: str = "v2_test.db"):
    db_file = tmp_path / name
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_v2_column_upgrades(conn)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    return db_file, engine, session_factory, override_get_db


class _MockAIProvider(BaseAIProvider):
    def __init__(self, fail: bool = False):
        super().__init__("ollama")
        self.fail = fail
        self.calls: List[Dict[str, Any]] = []

    async def check_health(self) -> dict:
        return {"provider": "ollama", "available": not self.fail, "models_count": 1}

    async def list_models(self) -> list:
        return [{"name": "qwen2.5:3b", "provider": "ollama", "is_default": True}]

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        context_window: int = 8192,
    ) -> AsyncGenerator[str, None]:
        yield "Mock response"

    async def complete_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        context_window: int = 8192,
    ) -> str:
        return "Mock reply."

    async def stream_chat_with_metrics(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        context_window: int = 8192,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        self.calls.append({"messages": messages, "model": model, "temperature": temperature, "context_window": context_window})
        if self.fail:
            yield {
                "type": "error",
                "error_category": "provider_unreachable",
                "error_message": "Simulated upstream outage",
                "user_message": "Provider temporarily unavailable.",
            }
            return
        yield {"type": "token", "text": "Mock "}
        yield {"type": "token", "text": "reply."}
        yield {
            "type": "done",
            "prompt_tokens": 12,
            "completion_tokens": 8,
            "total_tokens": 20,
        }


@pytest.mark.asyncio
async def test_owner_bootstrap_and_role_isolation(tmp_path, monkeypatch):
    _, engine, session_factory, override_get_db = await _make_isolated_db(tmp_path, "bootstrap.db")
    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(settings, "ADMIN_BOOTSTRAP_TOKEN", "top-secret-bootstrap-token")
    rate_limiter.clear()

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            status_res = await client.get("/api/auth/bootstrap-status")
            assert status_res.status_code == 200
            status_body = status_res.json()
            assert status_body["owner_exists"] is False
            assert status_body["requires_bootstrap_token"] is True
            assert status_body["web_bootstrap_allowed"] is True

            # Ordinary registration always forces role="user"
            reg_res = await client.post(
                "/api/auth/register",
                json={"username": "regular_user", "email": "regular@example.com", "password": "Password123!"},
            )
            assert reg_res.status_code == 201
            assert reg_res.json()["user"]["role"] == "user"

            # Ordinary user rejected at admin login
            denied_admin_login = await client.post(
                "/api/auth/admin-login",
                json={"email": "regular@example.com", "password": "Password123!"},
            )
            assert denied_admin_login.status_code == 403

            # Bootstrap fails with wrong token
            bad_boot = await client.post(
                "/api/auth/bootstrap-owner",
                json={
                    "username": "platform_owner",
                    "email": "owner@example.com",
                    "password": "OwnerPassword123!",
                    "bootstrap_token": "wrong-token",
                },
            )
            assert bad_boot.status_code == 403

            # Bootstrap succeeds once with valid token
            ok_boot = await client.post(
                "/api/auth/bootstrap-owner",
                json={
                    "username": "platform_owner",
                    "email": "owner@example.com",
                    "password": "OwnerPassword123!",
                    "bootstrap_token": "top-secret-bootstrap-token",
                },
            )
            assert ok_boot.status_code == 201
            assert ok_boot.json()["user"]["role"] == "owner"

            # Further bootstrap calls permanently locked
            second_boot = await client.post(
                "/api/auth/bootstrap-owner",
                json={
                    "username": "attacker_owner",
                    "email": "attacker@example.com",
                    "password": "OwnerPassword123!",
                    "bootstrap_token": "top-secret-bootstrap-token",
                },
            )
            assert second_boot.status_code == 403

            # Owner can sign in via admin-login
            owner_login = await client.post(
                "/api/auth/admin-login",
                json={"email": "owner@example.com", "password": "OwnerPassword123!"},
            )
            assert owner_login.status_code == 200
            assert owner_login.json()["user"]["role"] == "owner"

        # CLI bootstrap respects existing owner lock
        async def noop_init():
            return None

        monkeypatch.setattr(cli_bootstrap, "init_db", noop_init)
        monkeypatch.setattr(cli_bootstrap, "AsyncSessionLocal", session_factory)
        cli_rc = await cli_bootstrap.run_bootstrap("cli_owner", "cli@example.com", "StrongPass123!")
        assert cli_rc == 1
    finally:
        rate_limiter.clear()
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_cli_bootstrap_empty_db(tmp_path, monkeypatch):
    _, engine, session_factory, _ = await _make_isolated_db(tmp_path, "cli_empty.db")
    try:
        async def noop_init():
            return None

        monkeypatch.setattr(cli_bootstrap, "init_db", noop_init)
        monkeypatch.setattr(cli_bootstrap, "AsyncSessionLocal", session_factory)
        rc = await cli_bootstrap.run_bootstrap("root_owner", "root@test.local", "RootPass123!")
        assert rc == 0

        async with session_factory() as session:
            user = await UserRepository(session).get_by_email("root@test.local")
            assert user is not None
            assert user.role == "owner"
            assert user.is_active is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_admin_routes_strict_authorization_and_account_suspension(tmp_path):
    _, engine, session_factory, override_get_db = await _make_isolated_db(tmp_path, "admin_authz.db")
    app.dependency_overrides[get_db] = override_get_db
    rate_limiter.clear()

    try:
        async with session_factory() as session:
            repo = UserRepository(session)
            owner = await repo.create("the_owner", "owner@test.local", hash_password("Pass1234!"), role="owner")
            member = await repo.create("member_one", "member@test.local", hash_password("Pass1234!"), role="user")

        owner_token = create_access_token({"sub": owner.id, "role": "owner"})
        member_token = create_access_token({"sub": member.id, "role": "user"})

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            protected_endpoints = [
                ("GET", "/api/admin/users"),
                ("GET", "/api/admin/analytics"),
                ("GET", "/api/admin/monitoring"),
                ("GET", "/api/admin/intelligence"),
            ]
            for method, path in protected_endpoints:
                unauth = await client.request(method, path)
                assert unauth.status_code == 401
                ordinary = await client.request(method, path, headers={"Authorization": f"Bearer {member_token}"})
                assert ordinary.status_code == 403

            cfg_denied = await client.post(
                "/api/models/configure",
                headers={"Authorization": f"Bearer {member_token}"},
                json={"provider": "openai", "api_key": "sk-test"},
            )
            assert cfg_denied.status_code == 403

            # Owner lists users
            users_res = await client.get(
                "/api/admin/users?search=member",
                headers={"Authorization": f"Bearer {owner_token}"},
            )
            assert users_res.status_code == 200
            assert users_res.json()["total"] == 1
            assert users_res.json()["items"][0]["username"] == "member_one"

            # Owner cannot self-suspend or demote last owner
            self_suspend = await client.patch(
                f"/api/admin/users/{owner.id}/status",
                headers={"Authorization": f"Bearer {owner_token}"},
                json={"is_active": False},
            )
            assert self_suspend.status_code == 400

            demote_last = await client.patch(
                f"/api/admin/users/{owner.id}/role",
                headers={"Authorization": f"Bearer {owner_token}"},
                json={"role": "user"},
            )
            assert demote_last.status_code == 400

            # Owner suspends ordinary user -> login + JWT rejected
            suspend_res = await client.patch(
                f"/api/admin/users/{member.id}/status",
                headers={"Authorization": f"Bearer {owner_token}"},
                json={"is_active": False},
            )
            assert suspend_res.status_code == 200
            assert suspend_res.json()["is_active"] is False

            blocked_login = await client.post(
                "/api/auth/login",
                json={"email": "member@test.local", "password": "Pass1234!"},
            )
            assert blocked_login.status_code == 403

            blocked_jwt = await client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {member_token}"},
            )
            assert blocked_jwt.status_code == 403

            # Reactivate restores access
            reactivate = await client.patch(
                f"/api/admin/users/{member.id}/status",
                headers={"Authorization": f"Bearer {owner_token}"},
                json={"is_active": True},
            )
            assert reactivate.status_code == 200
            assert reactivate.json()["is_active"] is True

            restored_me = await client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {member_token}"},
            )
            assert restored_me.status_code == 200
    finally:
        rate_limiter.clear()
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_cross_user_and_guest_data_isolation(tmp_path):
    _, engine, session_factory, override_get_db = await _make_isolated_db(tmp_path, "isolation.db")
    app.dependency_overrides[get_db] = override_get_db
    rate_limiter.clear()
    uploaded_paths: List[str] = []

    try:
        async with session_factory() as session:
            repo = UserRepository(session)
            user_a = await repo.create("alice", "alice@test.local", hash_password("Pass1234!"), role="user")
            user_b = await repo.create("bob", "bob@test.local", hash_password("Pass1234!"), role="user")

        token_a = create_access_token({"sub": user_a.id, "role": "user"})
        token_b = create_access_token({"sub": user_b.id, "role": "user"})

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Guest conversation
            guest_conv = (await client.post("/api/conversations", json={"title": "Guest Secret"})).json()
            # User A conversation, memory, and document
            a_conv = (
                await client.post(
                    "/api/conversations",
                    headers={"Authorization": f"Bearer {token_a}"},
                    json={"title": "Alice Secret"},
                )
            ).json()
            a_mem = (
                await client.post(
                    "/api/memory",
                    headers={"Authorization": f"Bearer {token_a}"},
                    json={"content": "Alice private preference", "category": "preference"},
                )
            ).json()
            a_doc_res = await client.post(
                "/api/documents/upload",
                headers={"Authorization": f"Bearer {token_a}"},
                files={"file": ("secret_notes.txt", b"Confidential project roadmap details.", "text/plain")},
            )
            assert a_doc_res.status_code == 201
            a_doc = a_doc_res.json()

            async with session_factory() as session:
                doc_row = (await session.execute(select(Document).where(Document.id == a_doc["id"]))).scalar_one()
                if doc_row.storage_path:
                    uploaded_paths.append(doc_row.storage_path)

            # User B cannot see Alice's data in listings
            b_convs = (await client.get("/api/conversations", headers={"Authorization": f"Bearer {token_b}"})).json()
            assert [c["id"] for c in b_convs] == []
            b_mems = (await client.get("/api/memory", headers={"Authorization": f"Bearer {token_b}"})).json()
            assert b_mems == []
            b_docs = (await client.get("/api/documents", headers={"Authorization": f"Bearer {token_b}"})).json()
            assert b_docs == []

            # Guest cannot see Alice's conversation in listing
            guest_convs = (await client.get("/api/conversations")).json()
            assert all(c["id"] != a_conv["id"] for c in guest_convs)

            # User B gets 403 on direct access/modification of Alice's and Guest's resources
            for forbidden_req in [
                client.get(f"/api/conversations/{a_conv['id']}", headers={"Authorization": f"Bearer {token_b}"}),
                client.patch(f"/api/conversations/{a_conv['id']}", headers={"Authorization": f"Bearer {token_b}"}, json={"title": "Stolen"}),
                client.delete(f"/api/conversations/{a_conv['id']}", headers={"Authorization": f"Bearer {token_b}"}),
                client.get(f"/api/conversations/{guest_conv['id']}", headers={"Authorization": f"Bearer {token_b}"}),
                client.patch(f"/api/memory/{a_mem['id']}", headers={"Authorization": f"Bearer {token_b}"}, json={"content": "Tampered"}),
                client.delete(f"/api/memory/{a_mem['id']}", headers={"Authorization": f"Bearer {token_b}"}),
                client.get(f"/api/documents/{a_doc['id']}", headers={"Authorization": f"Bearer {token_b}"}),
                client.delete(f"/api/documents/{a_doc['id']}", headers={"Authorization": f"Bearer {token_b}"}),
            ]:
                resp = await forbidden_req
                assert resp.status_code == 403

            # RAG query scoped by user_id cannot retrieve Alice's chunks
            b_rag = await client.post(
                "/api/documents/query",
                headers={"Authorization": f"Bearer {token_b}"},
                json={"query": "roadmap"},
            )
            assert b_rag.status_code == 200
            assert b_rag.json()["total_found"] == 0
    finally:
        for path in uploaded_paths:
            if os.path.exists(path):
                os.remove(path)
        rate_limiter.clear()
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_intelligence_core_pinning_prompts_and_agent_guard(tmp_path, monkeypatch):
    _, engine, session_factory, override_get_db = await _make_isolated_db(tmp_path, "intelligence.db")
    app.dependency_overrides[get_db] = override_get_db
    mock_provider = _MockAIProvider(fail=False)
    monkeypatch.setattr(chat_routes, "get_ai_provider", lambda name="ollama": mock_provider)
    rate_limiter.clear()

    try:
        async with session_factory() as session:
            repo = UserRepository(session)
            owner = await repo.create("core_owner", "core_owner@test.local", hash_password("Pass1234!"), role="owner")
            user = await repo.create("core_user", "core_user@test.local", hash_password("Pass1234!"), role="user")

        owner_token = create_access_token({"sub": owner.id, "role": "owner"})
        user_token = create_access_token({"sub": user.id, "role": "user"})

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            pub = (await client.get("/api/intelligence/public")).json()
            assert pub["active_model"] == settings.DEFAULT_MODEL
            assert pub["allow_user_model_switching"] is False

            # Ordinary user requests arbitrary model -> server enforces pinned model
            chat_res = await client.post(
                "/api/chat",
                headers={"Authorization": f"Bearer {user_token}"},
                json={"message": "Hello AUREVON", "model": "rogue-unpinned-model:99b", "stream": True},
            )
            assert chat_res.status_code == 200
            assert len(mock_provider.calls) == 1
            assert mock_provider.calls[0]["model"] == settings.DEFAULT_MODEL

            # Owner inspects keys (booleans only) & creates new master system prompt version
            intel_res = await client.get("/api/admin/intelligence", headers={"Authorization": f"Bearer {owner_token}"})
            assert intel_res.status_code == 200
            key_flags = intel_res.json()["provider_keys_configured"]
            assert all(isinstance(v, bool) for v in key_flags.values())

            prompt_res = await client.post(
                "/api/admin/intelligence/prompts",
                headers={"Authorization": f"Bearer {owner_token}"},
                json={
                    "name": "AUREVON Strict Core v2",
                    "content": "You are AUREVON v2 custom test prompt. Prioritize direct factual answers.",
                    "notes": "Test prompt activation",
                    "activate": True,
                },
            )
            assert prompt_res.status_code == 201
            assert len(prompt_res.json()["prompt_versions"]) == 2
            assert prompt_res.json()["active_prompt"]["name"] == "AUREVON Strict Core v2"

            # Subsequent chat receives the activated v2 master system instruction
            await client.post(
                "/api/chat",
                headers={"Authorization": f"Bearer {user_token}"},
                json={"message": "Second prompt check", "stream": True},
            )
            system_msg = mock_provider.calls[1]["messages"][0]["content"]
            assert "AUREVON v2 custom test prompt" in system_msg

            # Owner disables agent tool execution -> /api/agents/run returns 403
            toggle_res = await client.patch(
                "/api/admin/intelligence",
                headers={"Authorization": f"Bearer {owner_token}"},
                json={"enable_agent_tools": False},
            )
            assert toggle_res.status_code == 200
            agent_res = await client.post(
                "/api/agents/run",
                headers={"Authorization": f"Bearer {user_token}"},
                json={"task": "Calculate 2 + 2"},
            )
            assert agent_res.status_code == 403
    finally:
        rate_limiter.clear()
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_telemetry_privacy_analytics_and_system_monitoring(tmp_path, monkeypatch):
    _, engine, session_factory, override_get_db = await _make_isolated_db(tmp_path, "analytics.db")
    app.dependency_overrides[get_db] = override_get_db
    rate_limiter.clear()
    error_tracker.clear()

    try:
        async with session_factory() as session:
            repo = UserRepository(session)
            owner = await repo.create("obs_owner", "obs_owner@test.local", hash_password("Pass1234!"), role="owner")
            user = await repo.create("obs_user", "obs_user@test.local", hash_password("Pass1234!"), role="user")

        owner_token = create_access_token({"sub": owner.id, "role": "owner"})
        user_token = create_access_token({"sub": user.id, "role": "user"})

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Empty metrics distinguish unavailable (None) from invented zeros
            empty_analytics = await client.get(
                "/api/admin/analytics?range=7d",
                headers={"Authorization": f"Bearer {owner_token}"},
            )
            assert empty_analytics.status_code == 200
            empty_data = empty_analytics.json()
            assert empty_data["overview"]["total_ai_requests"] == 0
            assert empty_data["overview"]["success_rate_pct"] is None
            assert empty_data["performance"]["avg_latency_ms"] is None
            assert empty_data["performance"]["median_latency_ms"] is None
            assert empty_data["performance"]["p95_latency_ms"] is None
            assert empty_data["performance"]["total_tokens"] is None

            # 2. Successful stream captures tokens & timing without storing prompt content
            secret_prompt = "TOP_SECRET_USER_PROMPT_XYZ_98765"
            monkeypatch.setattr(chat_routes, "get_ai_provider", lambda name="ollama": _MockAIProvider(fail=False))
            ok_chat = await client.post(
                "/api/chat",
                headers={"Authorization": f"Bearer {user_token}"},
                json={"message": secret_prompt, "stream": True},
            )
            assert ok_chat.status_code == 200
            assert '"delta": "Mock "' in ok_chat.text
            assert '"delta": "reply."' in ok_chat.text
            assert '"total_tokens": 20' in ok_chat.text

            # 3. Failed stream logs structured error category
            monkeypatch.setattr(chat_routes, "get_ai_provider", lambda name="ollama": _MockAIProvider(fail=True))
            err_chat = await client.post(
                "/api/chat",
                headers={"Authorization": f"Bearer {user_token}"},
                json={"message": "Will fail cleanly", "stream": True},
            )
            assert err_chat.status_code == 200

            async with session_factory() as session:
                logs = list((await session.execute(select(AIRequestLog).order_by(AIRequestLog.created_at.asc()))).scalars().all())
                assert len(logs) == 2
                assert logs[0].success is True
                assert logs[0].prompt_tokens == 12
                assert logs[0].completion_tokens == 8
                assert logs[0].total_tokens == 20
                assert secret_prompt not in (logs[0].error_message or "")
                assert logs[1].success is False
                assert logs[1].error_category == "provider_unreachable"

            # 4. Aggregated analytics across 24h & custom range
            analytics_res = await client.get(
                "/api/admin/analytics?range=24h",
                headers={"Authorization": f"Bearer {owner_token}"},
            )
            assert analytics_res.status_code == 200
            a_data = analytics_res.json()
            assert a_data["overview"]["total_ai_requests"] == 2
            assert a_data["overview"]["successful_requests"] == 1
            assert a_data["overview"]["failed_requests"] == 1
            assert a_data["overview"]["success_rate_pct"] == 50.0
            assert a_data["performance"]["total_tokens"] == 20
            assert a_data["performance"]["median_latency_ms"] is not None
            assert a_data["error_breakdown"][0]["error_category"] == "provider_unreachable"
            assert len(a_data["time_series"]) >= 24
            assert sum(pt["requests"] for pt in a_data["time_series"]) == 2
            assert sum(pt["total_tokens"] for pt in a_data["time_series"]) == 20

            custom_res = await client.get(
                "/api/admin/analytics?range=custom&start_date=2026-01-01T00:00:00Z&end_date=2026-12-31T23:59:59Z",
                headers={"Authorization": f"Bearer {owner_token}"},
            )
            assert custom_res.status_code == 200

            # 5. Live system monitoring returns DB connectivity, RAM/CPU telemetry, and recent failures
            import logging as py_logging
            py_logging.getLogger("aurevon.test").error("Simulated runtime error sample")

            mon_res = await client.get("/api/admin/monitoring", headers={"Authorization": f"Bearer {owner_token}"})
            assert mon_res.status_code == 200
            mon = mon_res.json()
            assert mon["database_connected"] is True
            assert mon["backend_status"] == "healthy"
            assert len(mon["recent_failed_ai_requests"]) == 1
            assert any("Simulated runtime error sample" in item["message"] for item in mon["recent_app_errors"])
    finally:
        error_tracker.clear()
        rate_limiter.clear()
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_sliding_window_rate_limit_enforced(tmp_path, monkeypatch):
    _, engine, _, override_get_db = await _make_isolated_db(tmp_path, "ratelimit.db")
    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_PER_MINUTE", 2)
    rate_limiter.clear()

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r1 = await client.post("/api/auth/login", json={"email": "none@test.local", "password": "wrong"})
            r2 = await client.post("/api/auth/login", json={"email": "none@test.local", "password": "wrong"})
            r3 = await client.post("/api/auth/login", json={"email": "none@test.local", "password": "wrong"})
            assert r1.status_code == 401
            assert r2.status_code == 401
            assert r3.status_code == 429
    finally:
        rate_limiter.clear()
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_non_destructive_v2_migration_and_alembic_cli(tmp_path):
    # Part A: Simulated pre-V2 schema lacking role, is_active, last_active_at
    legacy_db = tmp_path / "legacy_v1.db"
    raw_conn = sqlite3.connect(legacy_db)
    raw_conn.executescript(
        """
        CREATE TABLE users (
            id VARCHAR(36) PRIMARY KEY,
            username VARCHAR(64) NOT NULL UNIQUE,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at DATETIME NOT NULL
        );
        CREATE TABLE conversations (
            id VARCHAR(36) PRIMARY KEY,
            user_id VARCHAR(36),
            title VARCHAR(255) NOT NULL,
            model VARCHAR(100) NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );
        CREATE TABLE messages (
            id VARCHAR(36) PRIMARY KEY,
            conversation_id VARCHAR(36) NOT NULL,
            role VARCHAR(32) NOT NULL,
            content TEXT NOT NULL,
            model VARCHAR(100),
            created_at DATETIME NOT NULL
        );
        INSERT INTO users (id, username, email, password_hash, created_at)
        VALUES ('u-1', 'v1_member', 'v1@test.local', 'hash', '2026-01-01 00:00:00');
        INSERT INTO conversations (id, user_id, title, model, created_at, updated_at)
        VALUES ('c-1', 'u-1', 'Preserved V1 Chat', 'qwen2.5:3b', '2026-01-01 00:00:00', '2026-01-01 00:00:00');
        INSERT INTO messages (id, conversation_id, role, content, model, created_at)
        VALUES ('m-1', 'c-1', 'user', 'Keep my history intact', 'qwen2.5:3b', '2026-01-01 00:00:00');
        """
    )
    raw_conn.commit()
    raw_conn.close()

    legacy_engine = create_async_engine(f"sqlite+aiosqlite:///{legacy_db.as_posix()}")
    try:
        async with legacy_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await _apply_v2_column_upgrades(conn)

        async with legacy_engine.connect() as conn:
            row = (await conn.execute(text("SELECT username, role, is_active FROM users WHERE id = 'u-1'"))).one()
            assert row[0] == "v1_member"
            assert row[1] == "user"
            assert bool(row[2]) is True
            msg = (await conn.execute(text("SELECT content FROM messages WHERE id = 'm-1'"))).scalar_one()
            assert msg == "Keep my history intact"
    finally:
        await legacy_engine.dispose()

    # Part B: Real aurevon.db copy preserves every existing row through Alembic upgrade
    repo_root = Path(__file__).resolve().parents[2]
    live_db = repo_root / "aurevon.db"
    if live_db.exists():
        copy_db = tmp_path / "aurevon_copy.db"
        shutil.copy2(live_db, copy_db)
        before = sqlite3.connect(copy_db)
        before_counts = {
            tbl: before.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            for tbl in ("users", "conversations", "messages")
        }
        before.close()

        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite+aiosqlite:///{copy_db.as_posix()}"
        proc_copy = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc_copy.returncode == 0, proc_copy.stderr

        after = sqlite3.connect(copy_db)
        for tbl, count in before_counts.items():
            assert after.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0] == count
        after.close()

    # Part C: Fresh empty DB migrates cleanly via Alembic CLI
    fresh_db = tmp_path / "fresh_alembic.db"
    env_fresh = os.environ.copy()
    env_fresh["DATABASE_URL"] = f"sqlite+aiosqlite:///{fresh_db.as_posix()}"
    proc_fresh = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=str(repo_root),
        env=env_fresh,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_fresh.returncode == 0, proc_fresh.stderr

    fresh_conn = sqlite3.connect(fresh_db)
    tables = {r[0] for r in fresh_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    version = fresh_conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    fresh_conn.close()
    assert version == "20261112_0003"
    assert {
        "users",
        "conversations",
        "conversation_summaries",
        "messages",
        "ai_request_logs",
        "system_ai_configs",
        "system_prompt_versions",
        "revoked_tokens",
        "admin_audit_logs",
        "security_events",
        "api_request_logs",
        "platform_configs",
        "tool_configs",
        "tool_execution_logs",
        "provider_usage_logs",
    } <= tables
