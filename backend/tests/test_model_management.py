import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.database.session import init_db
from backend.app.services.ai.factory import ProviderFactory


@pytest.mark.asyncio
async def test_model_management_and_cloud_providers():
    await init_db()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Models List
        res = await client.get("/api/models")
        assert res.status_code == 200
        models = res.json()
        assert len(models) > 0
        assert any("qwen" in m["id"] for m in models)

        # 2. Providers Health
        health_res = await client.get("/api/models/health")
        assert health_res.status_code == 200
        health_list = health_res.json()
        assert isinstance(health_list, list)
        provider_names = [h["provider"] for h in health_list]
        assert "ollama" in provider_names
        assert "groq" in provider_names
        assert "openai" in provider_names

        # 3. Configure Cloud Provider API Key
        config_res = await client.post("/api/models/configure", json={
            "provider": "groq",
            "api_key": "gsk_test_mock_key_12345",
        })
        assert config_res.status_code == 200
        data = config_res.json()
        assert data["status"] == "configured"
        assert data["provider"] == "groq"
        assert "health" in data

        # Verify provider in factory has key set
        groq_provider = ProviderFactory.get_provider("groq")
        assert groq_provider.api_key == "gsk_test_mock_key_12345"
