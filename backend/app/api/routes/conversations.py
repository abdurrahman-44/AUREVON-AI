from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database.session import get_db
from backend.app.api.deps import get_optional_user, assert_resource_ownership
from backend.app.models.entities import User
from backend.app.repositories.conversation_repo import ConversationRepository
from backend.app.repositories.message_repo import MessageRepository
from backend.app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationDetailResponse,
)
from backend.app.schemas.message import MessageResponse

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("", response_model=List[ConversationResponse])
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ConversationRepository(db)
    user_id = current_user.id if current_user else None
    convs = await repo.list_conversations(user_id=user_id, limit=limit, offset=offset)
    
    results = []
    for c in convs:
        msg_count = len(c.messages) if c.messages else 0
        last_preview = c.messages[-1].content[:80] + ("..." if len(c.messages[-1].content) > 80 else "") if c.messages else None
        results.append(
            ConversationResponse(
                id=c.id,
                user_id=c.user_id,
                title=c.title,
                created_at=c.created_at,
                updated_at=c.updated_at,
                message_count=msg_count,
                last_message_preview=last_preview,
            )
        )
    return results


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ConversationRepository(db)
    user_id = current_user.id if current_user else None
    conv = await repo.create(title=payload.title or "New Conversation", user_id=user_id)
    return ConversationResponse(
        id=conv.id,
        user_id=conv.user_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=0,
        last_message_preview=None,
    )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ConversationRepository(db)
    conv = await repo.get_by_id(conversation_id, load_messages=True)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    assert_resource_ownership(conv.user_id, current_user, "conversation")
    
    messages = [
        MessageResponse(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            model=m.model,
            token_usage=m.token_usage,
            created_at=m.created_at,
        )
        for m in conv.messages
    ]
    return ConversationDetailResponse(
        id=conv.id,
        user_id=conv.user_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=messages,
    )


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    limit: int = 100,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ConversationRepository(db)
    conv = await repo.get_by_id(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    assert_resource_ownership(conv.user_id, current_user, "conversation")
    
    msg_repo = MessageRepository(db)
    messages = await msg_repo.get_messages_for_conversation(conversation_id, limit=limit)
    return [
        MessageResponse(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            model=m.model,
            token_usage=m.token_usage,
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    if not payload.title:
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    repo = ConversationRepository(db)
    existing = await repo.get_by_id(conversation_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Conversation not found")
    assert_resource_ownership(existing.user_id, current_user, "conversation")
    conv = await repo.update_title(conversation_id, payload.title.strip())
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationResponse(
        id=conv.id,
        user_id=conv.user_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ConversationRepository(db)
    existing = await repo.get_by_id(conversation_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Conversation not found")
    assert_resource_ownership(existing.user_id, current_user, "conversation")
    success = await repo.delete(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return None
