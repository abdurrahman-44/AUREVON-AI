from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.api.deps import get_optional_user, assert_resource_ownership
from backend.app.models.entities import Memory, User
from backend.app.schemas.memory import MemoryCreate, MemoryUpdate, MemoryResponse

router = APIRouter(prefix="/memory", tags=["Memory"])


@router.get("", response_model=List[MemoryResponse])
async def list_memories(
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Memory)
    if current_user:
        stmt = stmt.where(Memory.user_id == current_user.id)
    else:
        stmt = stmt.where(Memory.user_id.is_(None))
    stmt = stmt.order_by(Memory.updated_at.desc())
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    payload: MemoryCreate,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = current_user.id if current_user else None
    now = datetime.now(timezone.utc)
    mem = Memory(
        user_id=user_id,
        content=payload.content.strip(),
        category=(payload.category or "general").strip(),
        source=payload.source or "user",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(mem)
    await db.commit()
    await db.refresh(mem)
    return mem


@router.patch("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    payload: MemoryUpdate,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Memory).where(Memory.id == memory_id)
    res = await db.execute(stmt)
    mem = res.scalar_one_or_none()
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found")
    assert_resource_ownership(mem.user_id, current_user, "memory")

    if payload.content is not None:
        mem.content = payload.content.strip()
    if payload.category is not None:
        mem.category = payload.category.strip()
    if payload.is_active is not None:
        mem.is_active = payload.is_active

    mem.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(mem)
    return mem


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Memory).where(Memory.id == memory_id)
    res = await db.execute(stmt)
    mem = res.scalar_one_or_none()
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found")
    assert_resource_ownership(mem.user_id, current_user, "memory")

    await db.delete(mem)
    await db.commit()
    return None
