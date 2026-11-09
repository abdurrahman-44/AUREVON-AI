from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database.session import get_db
from backend.app.repositories.user_repo import UserRepository
from backend.app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
    UserSettingsResponse,
)
from backend.app.core.security import hash_password, verify_password, create_access_token
from backend.app.api.deps import get_current_user
from backend.app.models.entities import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


def build_user_response(user: User) -> UserResponse:
    settings_data = None
    if user.settings:
        settings_data = UserSettingsResponse(
            theme=user.settings.theme,
            default_model=user.settings.default_model,
            memory_enabled=user.settings.memory_enabled,
            other_preferences=user.settings.other_preferences or {},
        )
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        created_at=user.created_at,
        settings=settings_data,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)

    # Check for existing email or username
    if await repo.get_by_email(payload.email):
        raise HTTPException(status_code=400, detail="Email is already registered.")
    if await repo.get_by_username(payload.username):
        raise HTTPException(status_code=400, detail="Username is already taken.")

    pwd_hash = hash_password(payload.password)
    user = await repo.create(
        username=payload.username,
        email=payload.email,
        password_hash=pwd_hash,
    )

    token = create_access_token({"sub": user.id, "email": user.email, "username": user.username})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=build_user_response(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)

    # Support login with either email or username
    user = await repo.get_by_email(payload.email)
    if not user:
        user = await repo.get_by_username(payload.email)

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    token = create_access_token({"sub": user.id, "email": user.email, "username": user.username})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=build_user_response(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return build_user_response(user)


@router.post("/logout")
async def logout(user: User = Depends(get_current_user)):
    return {"message": "Successfully logged out."}
