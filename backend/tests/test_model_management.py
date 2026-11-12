import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.security import create_access_token, hash_password
from backend.app.database.session import Base, _apply_v2_column_upgrades, get_db
from backend.app.main import app
from backend.app.repositories.user_repo import UserRepository
from backend.app.services.ai.factory import ProviderFactory


@pytest.mark.asyncio
async def test_model_management_and_cloud_providers(tmp_path):
    db_file = tmp_path / "model_mgmt_test.db"
    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_v2_column_upgrades(conn)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    prev_groq_key = ProviderFactory.get_provider("groq").api_key

    try:
        async with TestSession() as session:
            repo = UserRepository(session)
            regular_user = await repo.create("model_user", "model_user@test.local", hash_password("pass1234"), role="user")
            owner_user = await repo.create("model_owner", "model_owner@test.local", hash_password("pass1234"), role="owner")

        user_token = create_access_token({"sub": regular_user.id, "role": "user"})
        owner_token = create_access_token({"sub": owner_user.id, "role": "owner"})

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Public Models List
            res = await client.get("/api/models")
            assert res.status_code == 200
            models = res.json()
            assert len(models) > 0
            assert any("qwen" in m["id"] for m in models)

            # 2. Public Providers Health
            health_res = await client.get("/api/models/health")
            assert health_res.status_code == 200
            health_list = health_res.json()
            assert isinstance(health_list, list)
            provider_names = [h["provider"] for h in health_list]
            assert "ollama" in provider_names
            assert "groq" in provider_names
            assert "openai" in provider_names

            # 3. Provider API key configuration requires owner role
            unauth_res = await client.post("/api/models/configure", json={
                "provider": "groq",
                "api_key": "gsk_test_mock_key_12345",
            })
            assert unauth_res.status_code == 401

            forbidden_res = await client.post(
                "/api/models/configure",
                headers={"Authorization": f"Bearer {user_token}"},
                json={"provider": "groq", "api_key": "gsk_test_mock_key_12345"},
            )
            assert forbidden_res.status_code == 403

            config_res = await client.post(
                "/api/models/configure",
                headers={"Authorization": f"Bearer {owner_token}"},
                json={"provider": "groq", "api_key": "gsk_test_mock_key_12345"},
            )
            assert config_res.status_code == 200
            data = config_res.json()
            assert data["status"] == "configured"
            assert data["provider"] == "groq"
            assert "health" in data

            groq_provider = ProviderFactory.get_provider("groq")
            assert groq_provider.api_key == "gsk_test_mock_key_12345"
    finally:
        app.dependency_overrides.pop(get_db, None)
        ProviderFactory.set_api_key("groq", prev_groq_key or "")
        await test_engine.dispose()
