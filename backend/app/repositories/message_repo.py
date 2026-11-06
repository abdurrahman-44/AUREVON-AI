from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, asc
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.entities import Message


class MessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        conversation_id: str,
        role: str,
        content: str,
        model: Optional[str] = None,
        token_usage: Optional[Dict[str, Any]] = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            model=model,
            token_usage=token_usage,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def get_messages_for_conversation(
        self,
        conversation_id: str,
        limit: int = 100,
    ) -> List[Message]:
        query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(asc(Message.created_at))
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
