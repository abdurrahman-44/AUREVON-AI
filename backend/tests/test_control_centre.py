import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.cache import app_cache
from backend.app.core.rate_limit import rate_limiter
from backend.app.core.security import _totp_at_counter, hash_password
from backend.app.database.session import Base, _apply_v2_column_upgrades, get_db
from backend.app.main import app
from backend.app.models.entities import (
    AIRequestLog,
    APIRequestLog,
    AdminAuditLog,
    Conversation,
    Message,
    SecurityEvent,
    User,
)
from backend.app.repositories.user_repo import UserRepository
from backend.app.schemas.model import ProviderHealth
from backend.app.services.ai.base import BaseAIProvider
from backend.app.services.ai.factory import ProviderFactory


async def _make_isolated_db(tmp_path: Path, name: str = "control_centre_test.db"):
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


class _DeterministicAIProvider(BaseAIProvider):
    def __init__(self, fail: bool = False):
        super().__init__("ollama")
        self.fail = fail

    async def check_health(self) -> ProviderHealth:
        return ProviderHealth(
            provider="ollama",
            url="http://127.0.0.1:11434",
            status="healthy" if not self.fail else "unavailable",
            available_models=["qwen2.5:3b"] if not self.fail else [],
            error_message=None if not self.fail else "Simulated provider offline",
        )

    async def list_models(self) -> list:
        return []

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        context_window: int = 8192,
    ) -> AsyncGenerator[str, None]:
        if self.fail:
            raise RuntimeError("Simulated inference error")
        yield "OK"

    async def complete_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        context_window: int = 8192,
    ) -> str:
        if self.fail:
            raise RuntimeError("Simulated inference error")
        return "OK"

    async def stream_chat_with_metrics(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        context_window: int = 8192,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if self.fail:
            yield {"type": "error", "message": "Simulated inference error"}
            return
        yield {"type": "token", "text": "OK — live probe verified"}
        yield {
            "type": "done",
            "prompt_tokens": 11,
            "completion_tokens": 5,
            "total_tokens": 16,
        }


async def _seed_owner_and_user(session_factory):
    async with session_factory() as session:
        repo = UserRepository(session)
        owner = await repo.create(
            username="rootowner",
            email="owner@control.local",
            password_hash=hash_password("OwnerPass#2026"),
            role="owner",
        )
        member = await repo.create(
            username="normaluser",
            email="user@control.local",
            password_hash=hash_password("UserPass#2026"),
            role="user",
        )
        return owner, member


@pytest.mark.asyncio
async def test_jwt_revocation_on_logout_and_2fa_lifecycle(tmp_path):
    _, engine, session_factory, override_db = await _make_isolated_db(tmp_path, "auth_2fa.db")
    app.dependency_overrides[get_db] = override_db
    rate_limiter.clear()
    app_cache.clear()

    try:
        await _seed_owner_and_user(session_factory)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Owner signs in without 2FA initially
            res_login = await client.post(
                "/api/auth/admin-login",
                json={"email": "owner@control.local", "password": "OwnerPass#2026"},
            )
            assert res_login.status_code == 200
            owner_token = res_login.json()["access_token"]
            headers = {"Authorization": f"Bearer {owner_token}"}

            # Token works before logout
            me_before = await client.get("/api/auth/me", headers=headers)
            assert me_before.status_code == 200

            # Setup TOTP 2FA
            st0 = await client.get("/api/admin/security/2fa/status", headers=headers)
            assert st0.status_code == 200
            assert st0.json()["totp_enabled"] is False

            setup = await client.post("/api/admin/security/2fa/setup", headers=headers)
            assert setup.status_code == 200
            secret = setup.json()["secret"]
            assert setup.json()["otpauth_uri"].startswith("otpauth://totp/")

            # Invalid TOTP rejected
            bad_enable = await client.post(
                "/api/admin/security/2fa/enable",
                headers=headers,
                json={"code": "000000"},
            )
            assert bad_enable.status_code == 400

            # Valid live TOTP enables 2FA
            valid_code = _totp_at_counter(secret, int(time.time()) // 30)
            ok_enable = await client.post(
                "/api/admin/security/2fa/enable",
                headers=headers,
                json={"code": valid_code},
            )
            assert ok_enable.status_code == 200
            assert ok_enable.json()["totp_enabled"] is True

            # Explicit logout revokes JWT JTI permanently
            out = await client.post("/api/auth/logout", headers=headers)
            assert out.status_code == 200

            me_after_logout = await client.get("/api/auth/me", headers=headers)
            assert me_after_logout.status_code == 401

            # 2FA login challenge works properly
            challenge = await client.post(
                "/api/auth/admin-login",
                json={"email": "owner@control.local", "password": "OwnerPass#2026"},
            )
            assert challenge.status_code == 401
            assert challenge.headers.get("X-AUREVON-2FA-Required") == "true"

            fresh_code = _totp_at_counter(secret, int(time.time()) // 30)
            res_2fa_login = await client.post(
                "/api/auth/admin-login",
                json={"email": "owner@control.local", "password": "OwnerPass#2026", "totp_code": fresh_code},
            )
            assert res_2fa_login.status_code == 200
            new_headers = {"Authorization": f"Bearer {res_2fa_login.json()['access_token']}"}

            # Disable 2FA cleanly
            disable_code = _totp_at_counter(secret, int(time.time()) // 30)
            disabled = await client.post(
                "/api/admin/security/2fa/disable",
                headers=new_headers,
                json={"code": disable_code},
            )
            assert disabled.status_code == 200
            assert disabled.json()["totp_enabled"] is False
    finally:
        app.dependency_overrides.clear()
        rate_limiter.clear()
        app_cache.clear()
        await engine.dispose()


@pytest.mark.asyncio
async def test_terminal_allowlist_injection_protection_and_confirmation(tmp_path):
    _, engine, session_factory, override_db = await _make_isolated_db(tmp_path, "terminal.db")
    app.dependency_overrides[get_db] = override_db
    rate_limiter.clear()
    app_cache.clear()
    orig_providers = ProviderFactory._providers.copy()

    try:
        ProviderFactory._providers["ollama"] = _DeterministicAIProvider(fail=False)
        await _seed_owner_and_user(session_factory)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            owner_login = await client.post(
                "/api/auth/admin-login",
                json={"email": "owner@control.local", "password": "OwnerPass#2026"},
            )
            owner_headers = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}

            user_login = await client.post(
                "/api/auth/login",
                json={"email": "user@control.local", "password": "UserPass#2026"},
            )
            user_headers = {"Authorization": f"Bearer {user_login.json()['access_token']}"}

            # Ordinary user blocked from terminal + logs security event
            denied = await client.post(
                "/api/admin/terminal/execute",
                headers=user_headers,
                json={"command": "help"},
            )
            assert denied.status_code == 403

            # Catalog & safe commands work
            catalog = await client.get("/api/admin/terminal/commands", headers=owner_headers)
            assert catalog.status_code == 200
            assert any(c["command"] == "cache clear" and c["requires_confirmation"] for c in catalog.json())

            for cmd in ("help", "status", "db stats", "users count", "system diagnostics", "ai test"):
                res = await client.post("/api/admin/terminal/execute", headers=owner_headers, json={"command": cmd})
                assert res.status_code == 200
                body = res.json()
                assert body["exit_code"] == 0, f"{cmd} failed: {body}"
                assert body["status"] == "ok"

            # Injection / arbitrary shell / SQL attempts strictly rejected
            for bad_cmd in (
                "status; rm -rf /",
                "ai status && cat .env",
                "db stats | grep users",
                "SELECT * FROM users",
                "$(whoami)",
            ):
                rej = await client.post(
                    "/api/admin/terminal/execute",
                    headers=owner_headers,
                    json={"command": bad_cmd},
                )
                assert rej.status_code == 200
                assert rej.json()["status"] == "rejected"
                assert rej.json()["exit_code"] == 1

            # Cache clear two-step server confirmation
            app_cache.set("smoke_key", {"ok": True}, ttl_seconds=60)
            step1 = await client.post(
                "/api/admin/terminal/execute",
                headers=owner_headers,
                json={"command": "cache clear"},
            )
            assert step1.status_code == 200
            s1 = step1.json()
            assert s1["requires_confirmation"] is True
            assert s1["confirm_token"]
            assert app_cache.get("smoke_key") == {"ok": True}

            step2 = await client.post(
                "/api/admin/terminal/execute",
                headers=owner_headers,
                json={"command": "cache clear", "confirm_token": s1["confirm_token"]},
            )
            assert step2.status_code == 200
            assert step2.json()["exit_code"] == 0
            assert app_cache.get("smoke_key") is None

            # Verify AdminAuditLog & SecurityEvent persisted
            audit_res = await client.get("/api/admin/logs/audit", headers=owner_headers)
            assert audit_res.status_code == 200
            assert audit_res.json()["total"] >= 10

            sec_res = await client.get("/api/admin/security/events", headers=owner_headers)
            assert sec_res.status_code == 200
            assert any(ev["event_type"] == "admin_access_denied" for ev in sec_res.json()["items"])
    finally:
        ProviderFactory._providers = orig_providers
        app.dependency_overrides.clear()
        rate_limiter.clear()
        app_cache.clear()
        await engine.dispose()


@pytest.mark.asyncio
async def test_analytics_90d_ai_test_user_detail_logs_and_platform_settings(tmp_path):
    _, engine, session_factory, override_db = await _make_isolated_db(tmp_path, "ops_full.db")
    app.dependency_overrides[get_db] = override_db
    rate_limiter.clear()
    app_cache.clear()
    orig_providers = ProviderFactory._providers.copy()

    try:
        ProviderFactory._providers["ollama"] = _DeterministicAIProvider(fail=False)
        owner, member = await _seed_owner_and_user(session_factory)

        # Seed user conversation, message (must NOT leak in user detail), and old telemetry log
        async with session_factory() as session:
            conv = Conversation(user_id=member.id, title="Private Topic")
            session.add(conv)
            await session.flush()
            session.add(
                Message(
                    conversation_id=conv.id,
                    role="user",
                    content="TOP_SECRET_CHAT_TEXT_MUST_NOT_APPEAR",
                    model="qwen2.5:3b",
                )
            )
            now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
            session.add(
                AIRequestLog(
                    user_id=member.id,
                    conversation_id=conv.id,
                    provider="ollama",
                    model="qwen2.5:3b",
                    duration_ms=210,
                    first_token_ms=45,
                    prompt_tokens=20,
                    completion_tokens=40,
                    total_tokens=60,
                    success=True,
                    created_at=now_naive,
                )
            )
            session.add(
                APIRequestLog(
                    method="GET",
                    path="/api/conversations",
                    status_code=200,
                    duration_ms=12,
                    created_at=now_naive - timedelta(days=45),
                )
            )
            await session.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            owner_login = await client.post(
                "/api/auth/admin-login",
                json={"email": "owner@control.local", "password": "OwnerPass#2026"},
            )
            owner_headers = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}

            user_login = await client.post(
                "/api/auth/login",
                json={"email": "user@control.local", "password": "UserPass#2026"},
            )
            user_headers = {"Authorization": f"Bearer {user_login.json()['access_token']}"}

            # 1. Analytics 90d & requests_today
            ana = await client.get("/api/admin/analytics?range=90d", headers=owner_headers)
            assert ana.status_code == 200
            ana_data = ana.json()
            assert ana_data["range_label"] == "90d"
            assert ana_data["overview"]["requests_today"] >= 1
            assert ana_data["overview"]["new_users"] >= 2

            # 2. Live AI test endpoint
            ai_probe = await client.post(
                "/api/admin/ai/test",
                headers=owner_headers,
                json={"provider": "ollama", "model": "qwen2.5:3b", "prompt": "Say OK"},
            )
            assert ai_probe.status_code == 200
            assert ai_probe.json()["success"] is True
            assert "OK" in (ai_probe.json()["response_preview"] or "")

            # 3. Privacy-safe User Detail
            detail = await client.get(f"/api/admin/users/{member.id}", headers=owner_headers)
            assert detail.status_code == 200
            detail_raw = detail.text
            detail_json = detail.json()
            assert detail_json["conversation_count"] == 1
            assert detail_json["message_count"] == 1
            assert detail_json["ai_request_count"] == 1
            assert "TOP_SECRET_CHAT_TEXT_MUST_NOT_APPEAR" not in detail_raw
            assert "password_hash" not in detail_json
            assert "totp_secret" not in detail_json

            # 4. System monitoring & diagnostics
            mon = await client.get("/api/admin/monitoring", headers=owner_headers)
            assert mon.status_code == 200
            assert mon.json()["uptime_seconds"] >= 0
            assert mon.json()["storage_total_gb"] is not None

            diag = await client.get("/api/admin/diagnostics", headers=owner_headers)
            assert diag.status_code == 200
            assert any(c["name"] == "Database Connectivity" and c["status"] == "pass" for c in diag.json()["checks"])

            # 5. API request telemetry + prune old records
            reqs = await client.get("/api/admin/logs/requests", headers=owner_headers)
            assert reqs.status_code == 200
            assert reqs.json()["total"] >= 1

            prune = await client.post(
                "/api/admin/logs/prune",
                headers=owner_headers,
                json={"retention_days": 30},
            )
            assert prune.status_code == 200
            assert prune.json()["deleted"]["api_request_logs_deleted"] >= 1

            # 6. Platform Settings: Signup disable & Maintenance mode
            patch_signup = await client.patch(
                "/api/admin/settings",
                headers=owner_headers,
                json={"allow_public_registration": False},
            )
            assert patch_signup.status_code == 200
            assert patch_signup.json()["allow_public_registration"] is False

            blocked_reg = await client.post(
                "/api/auth/register",
                json={"username": "lateuser", "email": "late@example.com", "password": "Password123!"},
            )
            assert blocked_reg.status_code == 403

            maint_on = await client.patch(
                "/api/admin/settings",
                headers=owner_headers,
                json={
                    "maintenance_mode": True,
                    "maintenance_message": "Maintenance window active.",
                },
            )
            assert maint_on.status_code == 200

            user_blocked = await client.get("/api/conversations", headers=user_headers)
            assert user_blocked.status_code == 503
            assert user_blocked.json()["maintenance_mode"] is True

            health_still_up = await client.get("/api/health")
            assert health_still_up.status_code == 200

            maint_off = await client.patch(
                "/api/admin/settings",
                headers=owner_headers,
                json={"maintenance_mode": False, "allow_public_registration": True},
            )
            assert maint_off.status_code == 200

            user_restored = await client.get("/api/conversations", headers=user_headers)
            assert user_restored.status_code == 200
    finally:
        ProviderFactory._providers = orig_providers
        app.dependency_overrides.clear()
        rate_limiter.clear()
        app_cache.clear()
        await engine.dispose()
