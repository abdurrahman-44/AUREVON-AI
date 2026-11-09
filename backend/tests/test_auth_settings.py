import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.database.session import init_db


@pytest.mark.asyncio
async def test_auth_and_user_settings_flow():
    await init_db()

    suffix = uuid.uuid4().hex[:8]
    user_a_email = f"neo_{suffix}@aurevon.ai"
    user_a_name = f"neo_{suffix}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register User A
        reg_payload = {
            "username": user_a_name,
            "email": user_a_email,
            "password": "SecurePassword123!",
        }
        res = await client.post("/api/auth/register", json=reg_payload)
        assert res.status_code == 201
        data_a = res.json()
        assert "access_token" in data_a
        assert data_a["user"]["username"] == user_a_name
        assert data_a["user"]["settings"]["theme"] == "dark"
        token_a = data_a["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # 2. Reject duplicate email/username
        dup_res = await client.post("/api/auth/register", json=reg_payload)
        assert dup_res.status_code == 400

        # 3. Login with correct credentials
        login_res = await client.post("/api/auth/login", json={
            "email": user_a_email,
            "password": "SecurePassword123!",
        })
        assert login_res.status_code == 200
        assert "access_token" in login_res.json()

        # 4. Login with wrong password
        fail_res = await client.post("/api/auth/login", json={
            "email": user_a_email,
            "password": "WrongPassword",
        })
        assert fail_res.status_code == 401

        # 5. Fetch /api/auth/me
        me_res = await client.get("/api/auth/me", headers=headers_a)
        assert me_res.status_code == 200
        assert me_res.json()["email"] == user_a_email

        # 6. User Settings: GET and PATCH
        settings_res = await client.get("/api/settings", headers=headers_a)
        assert settings_res.status_code == 200
        assert settings_res.json()["theme"] == "dark"

        update_settings_res = await client.patch("/api/settings", headers=headers_a, json={
            "theme": "light",
            "default_model": "qwen3:4b",
            "memory_enabled": False,
        })
        assert update_settings_res.status_code == 200
        updated = update_settings_res.json()
        assert updated["theme"] == "light"
        assert updated["default_model"] == "qwen3:4b"
        assert updated["memory_enabled"] is False

        # 7. User-scoped conversations test
        # User A creates a conversation
        conv_a_res = await client.post("/api/conversations", headers=headers_a, json={"title": "Neo Private Thread"})
        assert conv_a_res.status_code == 201
        conv_a_id = conv_a_res.json()["id"]

        # Register User B
        user_b_name = f"trinity_{suffix}"
        user_b_email = f"trinity_{suffix}@aurevon.ai"
        res_b = await client.post("/api/auth/register", json={
            "username": user_b_name,
            "email": user_b_email,
            "password": "PasswordTrinity99!",
        })
        assert res_b.status_code == 201
        token_b = res_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # User B lists conversations: should NOT see User A's thread
        list_b = await client.get("/api/conversations", headers=headers_b)
        assert list_b.status_code == 200
        b_convs = list_b.json()
        assert not any(c["id"] == conv_a_id for c in b_convs)

        # User A lists conversations: sees their thread
        list_a = await client.get("/api/conversations", headers=headers_a)
        assert list_a.status_code == 200
        a_convs = list_a.json()
        assert any(c["id"] == conv_a_id for c in a_convs)
