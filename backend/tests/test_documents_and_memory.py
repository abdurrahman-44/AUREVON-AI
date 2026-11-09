import pytest
import io
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.database.session import init_db


@pytest.mark.asyncio
async def test_documents_upload_and_rag():
    await init_db()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Upload sample technical specification document
        sample_doc_content = (
            "AUREVON AI Quantum Architecture Specification.\n"
            "The platform utilizes an independent model-agnostic inference engine.\n"
            "All embeddings are computed with normalized cosine similarity metrics.\n"
            "Storage relies on PostgreSQL with local zero-latency SQLite fallback."
        )
        file_payload = {
            "file": ("aurevon_spec.txt", sample_doc_content.encode("utf-8"), "text/plain")
        }

        upload_res = await client.post("/api/documents/upload", files=file_payload)
        assert upload_res.status_code == 201
        doc_data = upload_res.json()
        assert doc_data["filename"] == "aurevon_spec.txt"
        assert doc_data["processing_status"] == "completed"
        assert doc_data["chunk_count"] > 0
        doc_id = doc_data["id"]

        # 2. List documents
        list_res = await client.get("/api/documents")
        assert list_res.status_code == 200
        docs = list_res.json()
        assert any(d["id"] == doc_id for d in docs)

        # 3. Semantic Vector Search Query (RAG)
        query_res = await client.post("/api/documents/query", json={
            "query": "What database does AUREVON rely on?",
            "top_k": 3,
            "min_similarity": 0.1,
        })
        assert query_res.status_code == 200
        query_data = query_res.json()
        assert query_data["total_found"] > 0
        best_chunk = query_data["results"][0]
        assert "PostgreSQL" in best_chunk["content"]
        assert best_chunk["filename"] == "aurevon_spec.txt"

        # 4. Clean up / Delete document
        del_res = await client.delete(f"/api/documents/{doc_id}")
        assert del_res.status_code == 204


@pytest.mark.asyncio
async def test_memory_crud_and_retrieval():
    await init_db()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create a Memory
        mem_res = await client.post("/api/memory", json={
            "content": "User prefers concise architecture summaries with Mermaid diagrams.",
            "category": "preference",
            "source": "manual",
        })
        assert mem_res.status_code == 201
        mem_data = mem_res.json()
        assert mem_data["category"] == "preference"
        assert mem_data["is_active"] is True
        mem_id = mem_data["id"]

        # 2. List Memories
        list_res = await client.get("/api/memory")
        assert list_res.status_code == 200
        memories = list_res.json()
        assert any(m["id"] == mem_id for m in memories)

        # 3. Update Memory
        patch_res = await client.patch(f"/api/memory/{mem_id}", json={
            "category": "instruction",
            "is_active": False,
        })
        assert patch_res.status_code == 200
        updated = patch_res.json()
        assert updated["category"] == "instruction"
        assert updated["is_active"] is False

        # 4. Delete Memory
        del_res = await client.delete(f"/api/memory/{mem_id}")
        assert del_res.status_code == 204
