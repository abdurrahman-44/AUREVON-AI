from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from backend.app.core.config import settings
from backend.app.models.entities import User, UserSettings


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        username: str,
        email: str,
        password_hash: str,
        role: str = "user",
        is_active: bool = True,
    ) -> User:
        now = datetime.now(timezone.utc)
        user = User(
            username=username.lower().strip(),
            email=email.lower().strip(),
            password_hash=password_hash,
            role=role,
            is_active=is_active,
            last_active_at=now,
            created_at=now,
            updated_at=now,
        )
        self.session.add(user)
        await self.session.flush()

        # Initialize default settings
        user_settings = UserSettings(
            user_id=user.id,
            theme="dark",
            default_model=settings.DEFAULT_MODEL,
            memory_enabled=True,
            other_preferences={"system_prompt": "You are AUREVON AI, an intelligent, helpful, and precise assistant."},
            updated_at=now,
        )
        self.session.add(user_settings)
        await self.session.commit()
        await self.session.refresh(user)
        return await self.get_by_id(user.id)

    async def has_any_owner(self) -> bool:
        query = select(func.count(User.id)).where(User.role == "owner")
        result = await self.session.execute(query)
        return (result.scalar_one() or 0) > 0

    async def touch_last_active(self, user_id: str) -> None:
        now = datetime.now(timezone.utc)
        stmt = update(User).where(User.id == user_id).values(last_active_at=now)
        await self.session.execute(stmt)
        await self.session.commit()

    async def set_active_status(self, user_id: str, is_active: bool) -> Optional[User]:
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(is_active=is_active, updated_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
        await self.session.commit()
        return await self.get_by_id(user_id)

    async def set_role(self, user_id: str, role: str) -> Optional[User]:
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(role=role, updated_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
        await self.session.commit()
        return await self.get_by_id(user_id)

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
