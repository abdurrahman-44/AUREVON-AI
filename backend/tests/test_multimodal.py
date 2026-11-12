import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.security import create_access_token, hash_password
from backend.app.database.session import Base, _apply_v2_column_upgrades, get_db
from backend.app.main import app
from backend.app.repositories.user_repo import UserRepository
from backend.app.schemas.chat import ChatRequest


@pytest.mark.asyncio
async def test_chat_request_multimodal_schema():
    req = ChatRequest(
        message="What is in this diagram?",
        model="llava:7b",
        images=["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="],
    )
    assert req.message == "What is in this diagram?"
    assert req.images is not None
    assert len(req.images) == 1


@pytest.mark.asyncio
async def test_multimodal_vision_capability_check(tmp_path):
    db_file = tmp_path / "multimodal_test.db"
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

    try:
        async with TestSession() as session:
            repo = UserRepository(session)
            owner = await repo.create("mm_owner", "mm_owner@test.local", hash_password("pass1234"), role="owner")
        owner_token = create_access_token({"sub": owner.id, "role": "owner"})

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Server-pinned qwen2.5:3b (text-only) rejects images with capability notice even if client asks for llava:7b
            payload_pinned = {
                "message": "Explain this architecture diagram",
                "model": "llava:7b",
                "stream": True,
                "images": ["dummy_base64_data"],
            }
            res1 = await client.post("/api/chat", json=payload_pinned)
            assert res1.status_code == 200
            text1 = res1.text
            assert "Model Capability Notice" in text1
            assert "does not support image analysis" in text1

            # 2. Owner enables a vision model on the server -> capability check passes without text-only notice
            patch_res = await client.patch(
                "/api/admin/intelligence",
                headers={"Authorization": f"Bearer {owner_token}"},
                json={"active_provider": "ollama", "active_model": "llava:7b"},
            )
            assert patch_res.status_code == 200

            payload_vision = {
                "message": "Explain this diagram",
                "model": "llava:7b",
                "stream": True,
                "images": ["dummy_base64_data"],
            }
            res2 = await client.post("/api/chat", json=payload_vision)
            assert res2.status_code == 200
            text2 = res2.text
            assert "does not support image analysis" not in text2
    finally:
        app.dependency_overrides.pop(get_db, None)
        await test_engine.dispose()
