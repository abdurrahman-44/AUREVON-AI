from datetime import datetime, timedelta, timezone
import hmac
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_optional_token_payload
from backend.app.core.config import settings
from backend.app.core.rate_limit import rate_limit_dependency
from backend.app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
    verify_totp_code,
)
from backend.app.database.session import get_db
from backend.app.models.entities import RevokedToken, User
from backend.app.repositories.user_repo import UserRepository
from backend.app.schemas.auth import (
    BootstrapStatusResponse,
    OwnerBootstrapRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    UserSettingsResponse,
)
from backend.app.services.audit import extract_client_ip, record_admin_audit, record_security_event
from backend.app.services.platform_settings import PlatformSettingsService

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
        role=user.role,
        is_active=user.is_active,
        totp_enabled=bool(user.totp_enabled),
        last_active_at=user.last_active_at,
        created_at=user.created_at,
        settings=settings_data,
    )


def _issue_token(user: User, is_admin_session: bool = False) -> str:
    delta = timedelta(minutes=settings.ADMIN_SESSION_EXPIRE_MINUTES) if is_admin_session else None
    return create_access_token(
        {
            "sub": user.id,
            "email": user.email,
            "username": user.username,
            "role": user.role,
        },
        expires_delta=delta,
    )


async def _authenticate_user(
    repo: UserRepository,
    db: AsyncSession,
    identifier: str,
    password: str,
    request: Request,
    is_admin_attempt: bool = False,
) -> User:
    ip_addr = extract_client_ip(request)
    path = request.url.path
    user = await repo.get_by_email(identifier)
    if not user:
        user = await repo.get_by_username(identifier)

    if not user or not verify_password(password, user.password_hash):
        await record_security_event(
            db,
            event_type="admin_login_failed" if is_admin_attempt else "login_failed",
            severity="warning",
            user_id=user.id if user else None,
            identifier=identifier[:120],
            ip_address=ip_addr,
            path=path,
            detail="Invalid credentials supplied.",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    if not user.is_active:
        await record_security_event(
            db,
            event_type="suspended_login_blocked",
            severity="warning",
            user_id=user.id,
            identifier=user.username,
            ip_address=ip_addr,
            path=path,
            detail="Blocked authentication attempt on suspended account.",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been suspended. Please contact the platform administrator.",
        )

    await repo.touch_last_active(user.id)
    refreshed = await repo.get_by_id(user.id)
    return refreshed or user


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_dependency("auth_register", lambda: settings.RATE_LIMIT_AUTH_PER_MINUTE))],
)
async def register(payload: UserRegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    platform_cfg = await PlatformSettingsService.get_snapshot(db)
    if not platform_cfg.get("allow_public_registration", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public account registration is currently disabled by the platform administrator.",
        )

    repo = UserRepository(db)
    if await repo.get_by_email(payload.email):
        raise HTTPException(status_code=400, detail="Email is already registered.")
    if await repo.get_by_username(payload.username):
        raise HTTPException(status_code=400, detail="Username is already taken.")

    pwd_hash = hash_password(payload.password)
    user = await repo.create(
        username=payload.username,
        email=payload.email,
        password_hash=pwd_hash,
        role="user",
        is_active=True,
    )
    await record_security_event(
        db,
        event_type="user_registered",
        severity="info",
        user_id=user.id,
        identifier=user.username,
        ip_address=extract_client_ip(request),
        path=request.url.path,
        detail=f"Registered standard user account '{user.username}'.",
    )

    token = _issue_token(user)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=build_user_response(user),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit_dependency("auth_login", lambda: settings.RATE_LIMIT_AUTH_PER_MINUTE))],
)
async def login(payload: UserLoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    user = await _authenticate_user(repo, db, payload.email, payload.password, request, is_admin_attempt=False)
    await record_security_event(
        db,
        event_type="login_success",
        severity="info",
        user_id=user.id,
        identifier=user.username,
        ip_address=extract_client_ip(request),
        path=request.url.path,
        detail=f"Signed in user '{user.username}'.",
    )
    token = _issue_token(user)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=build_user_response(user),
    )


@router.post(
    "/admin-login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit_dependency("auth_admin_login", lambda: settings.RATE_LIMIT_AUTH_PER_MINUTE))],
)
async def admin_login(payload: UserLoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Dedicated administrator login endpoint enforcing owner role verification and optional TOTP 2FA."""
    repo = UserRepository(db)
    ip_addr = extract_client_ip(request)
    user = await _authenticate_user(repo, db, payload.email, payload.password, request, is_admin_attempt=True)

    if user.role != "owner":
        await record_security_event(
            db,
            event_type="admin_login_denied",
            severity="critical",
            user_id=user.id,
            identifier=user.username,
            ip_address=ip_addr,
            path=request.url.path,
            detail=f"Non-owner '{user.username}' attempted Control Centre login.",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner administrator privileges required.",
        )

    if user.totp_enabled:
        if not payload.totp_code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Two-factor authentication code required.",
                headers={"X-AUREVON-2FA-Required": "true"},
            )
        if not user.totp_secret or not verify_totp_code(user.totp_secret, payload.totp_code):
            await record_security_event(
                db,
                event_type="totp_failed",
                severity="critical",
                user_id=user.id,
                identifier=user.username,
                ip_address=ip_addr,
                path=request.url.path,
                detail=f"Invalid 2FA verification code on owner login for '{user.username}'.",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid two-factor authentication code.",
                headers={"X-AUREVON-2FA-Required": "true"},
            )

    await record_security_event(
        db,
        event_type="admin_login_success",
        severity="info",
        user_id=user.id,
        identifier=user.username,
        ip_address=ip_addr,
        path=request.url.path,
        detail=f"Owner '{user.username}' authenticated to Control Centre.",
    )
    await record_admin_audit(
        db,
        actor_user_id=user.id,
        actor_username=user.username,
        action="admin.login",
        target_type="session",
        target_id=user.id,
        summary=f"Owner signed in to Control Centre ({'with 2FA' if user.totp_enabled else 'password'})",
        ip_address=ip_addr,
    )

    token = _issue_token(user, is_admin_session=True)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=build_user_response(user),
    )


@router.get("/bootstrap-status", response_model=BootstrapStatusResponse)
async def get_bootstrap_status(db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    owner_exists = await repo.has_any_owner()
    requires_token = bool(settings.ADMIN_BOOTSTRAP_TOKEN)
    web_allowed = (not owner_exists) and (requires_token or settings.APP_ENV == "development")
    return BootstrapStatusResponse(
        owner_exists=owner_exists,
        requires_bootstrap_token=requires_token,
        web_bootstrap_allowed=web_allowed,
    )


@router.post("/bootstrap-owner", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def bootstrap_owner(payload: OwnerBootstrapRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """One-time secure initialization of the initial platform owner account."""
    repo = UserRepository(db)
    ip_addr = extract_client_ip(request)
    if await repo.has_any_owner():
        await record_security_event(
            db,
            event_type="bootstrap_blocked",
            severity="warning",
            identifier=payload.email[:120],
            ip_address=ip_addr,
            path=request.url.path,
            detail="Rejected owner bootstrap attempt because an owner already exists.",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform owner already exists. Owner bootstrap is permanently locked.",
        )

    configured_token = settings.ADMIN_BOOTSTRAP_TOKEN
    if configured_token:
        provided = payload.bootstrap_token or ""
        if not hmac.compare_digest(provided, configured_token):
            await record_security_event(
                db,
                event_type="bootstrap_invalid_token",
                severity="high",
                identifier=payload.email[:120],
                ip_address=ip_addr,
                path=request.url.path,
                detail="Rejected owner bootstrap due to invalid bootstrap token.",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid bootstrap token.",
            )
    elif settings.APP_ENV != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Web bootstrap requires ADMIN_BOOTSTRAP_TOKEN outside development mode. Use CLI bootstrap.",
        )

    if await repo.get_by_email(payload.email):
        raise HTTPException(status_code=400, detail="Email is already registered.")
    if await repo.get_by_username(payload.username):
        raise HTTPException(status_code=400, detail="Username is already taken.")

    pwd_hash = hash_password(payload.password)
    user = await repo.create(
        username=payload.username,
        email=payload.email,
        password_hash=pwd_hash,
        role="owner",
        is_active=True,
    )
    await record_security_event(
        db,
        event_type="bootstrap_success",
        severity="info",
        user_id=user.id,
        identifier=user.username,
        ip_address=ip_addr,
        path=request.url.path,
        detail=f"Initial platform owner '{user.username}' bootstrapped.",
    )
    await record_admin_audit(
        db,
        actor_user_id=user.id,
        actor_username=user.username,
        action="admin.bootstrap_owner",
        target_type="user",
        target_id=user.id,
        summary=f"Created initial platform owner '{user.username}'",
        ip_address=ip_addr,
    )

    token = _issue_token(user, is_admin_session=True)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=build_user_response(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return build_user_response(user)


@router.post("/logout")
async def logout(
    request: Request,
    user: User = Depends(get_current_user),
    token_payload: Optional[dict] = Depends(get_optional_token_payload),
    db: AsyncSession = Depends(get_db),
):
    """Revoke current JWT JTI cleanly so logged-out sessions cannot be replayed."""
    if token_payload and token_payload.get("jti"):
        exp_ts = token_payload.get("exp")
        expires_at = (
            datetime.fromtimestamp(exp_ts, tz=timezone.utc)
            if isinstance(exp_ts, (int, float))
            else None
        )
        db.add(
            RevokedToken(
                jti=str(token_payload["jti"]),
                user_id=user.id,
                expires_at=expires_at,
                revoked_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()

    await record_security_event(
        db,
        event_type="logout",
        severity="info",
        user_id=user.id,
        identifier=user.username,
        ip_address=extract_client_ip(request),
        path=request.url.path,
        detail=f"Signed out '{user.username}' and revoked session token.",
    )
    return {"message": "Successfully logged out."}
