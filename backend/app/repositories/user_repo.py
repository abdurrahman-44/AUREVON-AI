from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from backend.app.models.entities import User, UserSettings


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, username: str, email: str, password_hash: str) -> User:
        now = datetime.now(timezone.utc)
        user = User(
            username=username.lower().strip(),
            email=email.lower().strip(),
            password_hash=password_hash,
            created_at=now,
            updated_at=now,
        )
        self.session.add(user)
        await self.session.flush()

        # Initialize default settings
        settings = UserSettings(
            user_id=user.id,
            theme="dark",
            default_model="qwen2.5:3b",
            memory_enabled=True,
            other_preferences={"system_prompt": "You are AUREVON AI, an intelligent, helpful, and precise assistant."},
            updated_at=now,
        )
        self.session.add(settings)
        await self.session.commit()
        await self.session.refresh(user)
        return await self.get_by_id(user.id)

    async def get_by_id(self, user_id: str) -> Optional[User]:
        query = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.settings))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        query = (
            select(User)
            .where(User.email == email.lower().strip())
            .options(selectinload(User.settings))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        query = (
            select(User)
            .where(User.username == username.lower().strip())
            .options(selectinload(User.settings))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_settings(
        self,
        user_id: str,
        theme: Optional[str] = None,
        default_model: Optional[str] = None,
        memory_enabled: Optional[bool] = None,
        other_preferences: Optional[Dict[str, Any]] = None,
    ) -> Optional[UserSettings]:
        query = select(UserSettings).where(UserSettings.user_id == user_id)
        result = await self.session.execute(query)
        settings = result.scalar_one_or_none()
        if not settings:
            return None

        if theme is not None:
            settings.theme = theme
        if default_model is not None:
            settings.default_model = default_model
        if memory_enabled is not None:
            settings.memory_enabled = memory_enabled
        if other_preferences is not None:
            merged = dict(settings.other_preferences or {})
            merged.update(other_preferences)
            settings.other_preferences = merged

        settings.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(settings)
        return settings
