from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, asc, desc, func, delete
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
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        intent: Optional[str] = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            model=model,
            token_usage=token_usage,
            tool_calls=tool_calls,
            citations=citations,
            intent=intent,
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
        """Return up to the newest `limit` messages ordered chronologically [oldest -> newest]."""
        query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.created_at), desc(Message.id))
            .limit(limit)
        )
        result = await self.session.execute(query)
        rows = list(result.scalars().all())
        rows.reverse()
        return rows

    async def get_all_messages_for_conversation(
        self,
        conversation_id: str,
    ) -> List[Message]:
        query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(asc(Message.created_at), asc(Message.id))
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_message_count(self, conversation_id: str) -> int:
        res = await self.session.execute(
            select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
        )
        return int(res.scalar() or 0)

    async def delete_message(self, conversation_id: str, message_id: str) -> bool:
        res = await self.session.execute(
            delete(Message).where(Message.conversation_id == conversation_id, Message.id == message_id)
        )
        await self.session.commit()
        return bool(res.rowcount)
