import pytest
import json
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.database.session import init_db


@pytest.mark.asyncio
async def test_full_phase1_acceptance_lifecycle():
    """
    Validates all Phase 1 Foundation acceptance criteria:
    1. System health & AI provider check
    2. Available models check
    3. Conversation creation
    4. Sending a message and receiving a streamed SSE response
    5. Persistence of conversation & messages in database
    6. Continuing an existing conversation (multi-turn context)
    7. Multi-conversation history and isolation
    8. Conversation renaming and deletion
    """
    await init_db()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. System Health Check
        health_res = await client.get("/api/health")
        assert health_res.status_code == 200
        health_data = health_res.json()
        assert health_data["database"] == "connected"
        assert len(health_data["providers"]) > 0

        # 2. Models Discovery
        models_res = await client.get("/api/models")
        assert models_res.status_code == 200
        models_data = models_res.json()
        assert len(models_data) > 0
        model_ids = [m["id"] for m in models_data]
        assert any("qwen" in mid for mid in model_ids)

        # 3. Create a New Conversation
        conv_res = await client.post("/api/conversations", json={"title": "Phase 1 Foundation Test"})
        assert conv_res.status_code == 201
        conv_data = conv_res.json()
        conv_id = conv_data["id"]
        assert conv_data["title"] == "Phase 1 Foundation Test"

        # 4. Send Message & Stream Response (Turn 1)
        chat_payload = {
            "conversation_id": conv_id,
            "message": "Hello AUREVON, confirm system architecture status.",
            "model": "qwen2.5:3b",
            "temperature": 0.7,
            "stream": True,
        }

        streamed_chunks = []
        received_init = False
        received_done = False

        async with client.stream("POST", "/api/chat", json=chat_payload) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                event = json.loads(data_str)
                if "user_message_id" in event:
                    received_init = True
                if event.get("delta"):
                    streamed_chunks.append(event["delta"])
                if event.get("done"):
                    received_done = True
                    break

        assert received_init is True
        assert received_done is True
        assert len(streamed_chunks) > 0
        assistant_turn_1 = "".join(streamed_chunks)
        assert len(assistant_turn_1) > 0

        # 5. Conversation Persistence Verification (Simulating browser refresh)
        refresh_res = await client.get(f"/api/conversations/{conv_id}")
        assert refresh_res.status_code == 200
        refreshed_data = refresh_res.json()
        assert refreshed_data["id"] == conv_id
        # Must have exactly 2 messages: user prompt and assistant response
        assert len(refreshed_data["messages"]) == 2
        assert refreshed_data["messages"][0]["role"] == "user"
        assert refreshed_data["messages"][0]["content"] == "Hello AUREVON, confirm system architecture status."
        assert refreshed_data["messages"][1]["role"] == "assistant"
        assert refreshed_data["messages"][1]["content"] == assistant_turn_1

        # 6. Continue Existing Conversation (Turn 2)
        turn2_payload = {
            "conversation_id": conv_id,
            "message": "Acknowledged. List your active modules.",
            "model": "qwen2.5:3b",
            "temperature": 0.7,
            "stream": True,
        }

        turn2_chunks = []
        async with client.stream("POST", "/api/chat", json=turn2_payload) as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                if event.get("delta"):
                    turn2_chunks.append(event["delta"])
                if event.get("done"):
                    break

        assistant_turn_2 = "".join(turn2_chunks)
        assert len(assistant_turn_2) > 0

        # Verify multi-turn history retains 4 messages
        multi_turn_res = await client.get(f"/api/conversations/{conv_id}")
        assert multi_turn_res.status_code == 200
        multi_data = multi_turn_res.json()
        assert len(multi_data["messages"]) == 4
        assert multi_data["messages"][2]["role"] == "user"
        assert multi_data["messages"][3]["role"] == "assistant"

        # 7. Create Second Conversation & Verify Isolation
        conv2_res = await client.post("/api/conversations", json={"title": "Second Topic"})
        assert conv2_res.status_code == 201
        conv2_id = conv2_res.json()["id"]

        list_res = await client.get("/api/conversations")
        assert list_res.status_code == 200
        all_convs = list_res.json()
        ids = [c["id"] for c in all_convs]
        assert conv_id in ids
        assert conv2_id in ids

        # 8. Rename and Delete
        rename_res = await client.patch(f"/api/conversations/{conv_id}", json={"title": "Renamed Main Thread"})
        assert rename_res.status_code == 200
        assert rename_res.json()["title"] == "Renamed Main Thread"

        del_res = await client.delete(f"/api/conversations/{conv2_id}")
        assert del_res.status_code == 204

        # Confirm deleted
        check_del = await client.get(f"/api/conversations/{conv2_id}")
        assert check_del.status_code == 404
