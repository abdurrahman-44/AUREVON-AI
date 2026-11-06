import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.database.session import init_db


@pytest.mark.asyncio
async def test_health_and_root():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Test root
        res = await client.get("/")
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "AUREVON AI"
        assert data["status"] == "online"

        # Test health
        res = await client.get("/api/health")
        assert res.status_code == 200
        health_data = res.json()
        assert health_data["database"] == "connected"
        assert len(health_data["providers"]) > 0


@pytest.mark.asyncio
async def test_conversation_crud():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create conversation
        res = await client.post("/api/conversations", json={"title": "Test Chat"})
        assert res.status_code == 201
        created = res.json()
        conv_id = created["id"]
        assert created["title"] == "Test Chat"

        # List conversations
        res = await client.get("/api/conversations")
        assert res.status_code == 200
        conv_list = res.json()
        assert any(c["id"] == conv_id for c in conv_list)

        # Get conversation detail
        res = await client.get(f"/api/conversations/{conv_id}")
        assert res.status_code == 200
        detail = res.json()
        assert detail["id"] == conv_id
        assert detail["title"] == "Test Chat"

        # Update title
        res = await client.patch(f"/api/conversations/{conv_id}", json={"title": "Renamed Chat"})
        assert res.status_code == 200
        assert res.json()["title"] == "Renamed Chat"

        # Delete conversation
        res = await client.delete(f"/api/conversations/{conv_id}")
        assert res.status_code == 204

        # Verify deleted
        res = await client.get(f"/api/conversations/{conv_id}")
        assert res.status_code == 404
