import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.database.session import init_db


@pytest.mark.asyncio
async def test_web_research_endpoint():
    await init_db()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/research", json={
            "query": "Quantum computing qubit entanglement",
            "max_sources": 3,
        })
        assert res.status_code == 200
        data = res.json()
        assert data["query"] == "Quantum computing qubit entanglement"
        assert len(data["citations"]) > 0
        assert "summary" in data


@pytest.mark.asyncio
async def test_agent_tool_registry_and_execution():
    await init_db()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Inspect Tools
        tools_res = await client.get("/api/agents/tools")
        assert tools_res.status_code == 200
        tools = tools_res.json()
        tool_names = [t["name"] for t in tools]
        assert "calculator" in tool_names
        assert "code_analyzer" in tool_names
        assert "web_search" in tool_names
        assert "document_search" in tool_names

        # 2. Run Agent on Math Task
        math_run_res = await client.post("/api/agents/run", json={
            "task": "calculate (150 * 4) / 2 + 25",
        })
        assert math_run_res.status_code == 201
        run_data = math_run_res.json()
        assert run_data["status"] == "completed"
        assert len(run_data["execution_log"]) >= 3
        assert "325" in run_data["final_output"]
        run_id = run_data["id"]

        # 3. Retrieve Agent Run by ID
        get_res = await client.get(f"/api/agents/runs/{run_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == run_id

        # 4. Run Agent on Code Analysis Task
        code_snippet = (
            "def calculate_trajectory(velocity, angle):\n"
            "    import math\n"
            "    return velocity * math.sin(angle)\n"
        )
        code_run_res = await client.post("/api/agents/run", json={
            "task": f"analyze code:\n{code_snippet}",
        })
        assert code_run_res.status_code == 201
        code_data = code_run_res.json()
        assert code_data["status"] == "completed"
        assert "calculate_trajectory" in code_data["final_output"]

        # 5. List Runs
        list_res = await client.get("/api/agents/runs")
        assert list_res.status_code == 200
        runs = list_res.json()
        assert len(runs) >= 2
