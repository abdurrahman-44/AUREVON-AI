import pytest
import uuid
import json
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
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
async def test_multimodal_vision_capability_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Attempt image analysis with text-only model -> Should yield warning notice
        payload_text_only = {
            "message": "Explain this architecture diagram",
            "model": "qwen2.5:3b",
            "stream": True,
            "images": ["dummy_base64_data"],
        }
        res1 = await client.post("/api/chat", json=payload_text_only)
        assert res1.status_code == 200
        text1 = res1.text
        assert "Model Capability Notice" in text1
        assert "does not support image analysis" in text1

        # 2. Attempt image analysis with vision-enabled model (llava:7b)
        payload_vision = {
            "message": "Explain this diagram",
            "model": "llava:7b",
            "stream": True,
            "images": ["dummy_base64_data"],
        }
        res2 = await client.post("/api/chat", json=payload_vision)
        assert res2.status_code == 200
        text2 = res2.text
        # Notice that it shouldn't produce the capability notice:
        assert "does not support image analysis" not in text2
