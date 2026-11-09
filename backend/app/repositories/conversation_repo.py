from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, update, delete, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from backend.app.models.entities import Conversation, Message


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, title: str = "New Conversation", user_id: Optional[str] = None) -> Conversation:
        now = datetime.now(timezone.utc)
        conversation = Conversation(
            title=title,
            user_id=user_id,
            created_at=now,
            updated_at=now,
        )
        self.session.add(conversation)
        await self.session.commit()
        await self.session.refresh(conversation)
        return conversation

    async def get_by_id(self, conversation_id: str, load_messages: bool = False) -> Optional[Conversation]:
        query = select(Conversation).where(Conversation.id == conversation_id)
        if load_messages:
            query = query.options(selectinload(Conversation.messages))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_conversations(
        self,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Conversation]:
        query = select(Conversation).options(selectinload(Conversation.messages))
        if user_id:
            query = query.where(Conversation.user_id == user_id)
        query = query.order_by(desc(Conversation.updated_at)).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_title(self, conversation_id: str, title: str) -> Optional[Conversation]:
        conversation = await self.get_by_id(conversation_id)
        if not conversation:
            return None
        conversation.title = title
        conversation.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(conversation)
        return conversation

    async def touch(self, conversation_id: str) -> None:
        """Update updated_at timestamp when a message is added."""
        stmt = (
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def delete(self, conversation_id: str) -> bool:
        conversation = await self.get_by_id(conversation_id)
        if not conversation:
            return False
        await self.session.delete(conversation)
        await self.session.commit()
        return True
