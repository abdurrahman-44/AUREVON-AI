from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database.session import get_db
from backend.app.api.deps import get_current_user
from backend.app.repositories.user_repo import UserRepository
from backend.app.schemas.auth import UserSettingsResponse, UserSettingsUpdate
from backend.app.models.entities import User

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("", response_model=UserSettingsResponse)
async def get_user_settings(user: User = Depends(get_current_user)):
    if not user.settings:
        raise HTTPException(status_code=404, detail="Settings not found")
    return UserSettingsResponse(
        theme=user.settings.theme,
        default_model=user.settings.default_model,
        memory_enabled=user.settings.memory_enabled,
        other_preferences=user.settings.other_preferences or {},
    )


@router.patch("", response_model=UserSettingsResponse)
async def update_user_settings(
    payload: UserSettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepository(db)
    updated = await repo.update_settings(
        user_id=user.id,
        theme=payload.theme,
        default_model=payload.default_model,
        memory_enabled=payload.memory_enabled,
        other_preferences=payload.other_preferences,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Could not update settings")

    return UserSettingsResponse(
        theme=updated.theme,
        default_model=updated.default_model,
        memory_enabled=updated.memory_enabled,
        other_preferences=updated.other_preferences or {},
    )
