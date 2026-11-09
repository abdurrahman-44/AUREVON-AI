from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.api.deps import get_optional_user
from backend.app.models.entities import AgentRun, User
from backend.app.schemas.agent import AgentRunRequest, AgentRunResponse, ToolInfoResponse
from backend.app.services.agents.tools import ToolRegistry
from backend.app.services.agents.runner import AgentRunner

router = APIRouter(prefix="/agents", tags=["Agents"])

# In-memory tracking of active runners for cancellation
_active_runners = {}


@router.get("/tools", response_model=List[ToolInfoResponse])
async def list_agent_tools():
    """List sandboxed tools available to AI agents."""
    return ToolRegistry.list_available_tools()


@router.post("/run", response_model=AgentRunResponse, status_code=status.HTTP_201_CREATED)
async def run_agent(
    payload: AgentRunRequest,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = current_user.id if current_user else None
    now = datetime.now(timezone.utc)

    # 1. Create Run in DB
    run_record = AgentRun(
        user_id=user_id,
        task=payload.task.strip(),
        status="running",
        execution_log=[],
        created_at=now,
    )
    db.add(run_record)
    await db.commit()
    await db.refresh(run_record)

    # 2. Instantiate and run AgentRunner
    runner = AgentRunner(session=db, user_id=user_id)
    _active_runners[run_record.id] = runner

    try:
        outcome = await runner.execute_task(payload.task, model=payload.model)
        run_record.status = outcome["status"]
        run_record.execution_log = outcome["logs"]
        run_record.final_output = outcome["output"]
        run_record.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(run_record)
    finally:
        _active_runners.pop(run_record.id, None)

    return run_record


@router.get("/runs", response_model=List[AgentRunResponse])
async def list_agent_runs(
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AgentRun)
    if current_user:
        stmt = stmt.where(AgentRun.user_id == current_user.id)
    stmt = stmt.order_by(AgentRun.created_at.desc())
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.get("/runs/{run_id}", response_model=AgentRunResponse)
async def get_agent_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AgentRun).where(AgentRun.id == run_id)
    res = await db.execute(stmt)
    run_record = res.scalar_one_or_none()
    if not run_record:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return run_record


@router.post("/runs/{run_id}/cancel", response_model=AgentRunResponse)
async def cancel_agent_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    if run_id in _active_runners:
        _active_runners[run_id].cancel()

    stmt = select(AgentRun).where(AgentRun.id == run_id)
    res = await db.execute(stmt)
    run_record = res.scalar_one_or_none()
    if not run_record:
        raise HTTPException(status_code=404, detail="Agent run not found")

    run_record.status = "cancelled"
    run_record.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run_record)
    return run_record
