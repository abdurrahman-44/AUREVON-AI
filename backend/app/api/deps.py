from typing import Any, Dict, Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database.session import get_db
from backend.app.core.security import decode_access_token
from backend.app.repositories.user_repo import UserRepository
from backend.app.models.entities import RevokedToken, User
from backend.app.services.audit import extract_client_ip, record_security_event

security_scheme = HTTPBearer(auto_error=False)


async def get_optional_token_payload(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Optional[Dict[str, Any]]:
    if not credentials or not credentials.credentials:
        return None
    return decode_access_token(credentials.credentials)


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Retrieve active user from non-revoked JWT bearer token if present, otherwise None."""
    if not credentials or not credentials.credentials:
        return None

    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        return None

    jti = payload.get("jti")
    if jti:
        revoked = (
            await db.execute(select(RevokedToken.id).where(RevokedToken.jti == jti))
        ).scalar_one_or_none()
        if revoked is not None:
            return None

    user_id = payload["sub"]
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if user and not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been suspended. Please contact the platform administrator.",
        )
    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require valid authenticated active user."""
    user = await get_optional_user(credentials, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required or token expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require owner-level administrator privileges and log unauthorized elevation attempts."""
    if user.role != "owner":
        try:
            await record_security_event(
                db,
                event_type="admin_access_denied",
                severity="warning",
                user_id=user.id,
                identifier=user.username,
                ip_address=extract_client_ip(request),
                path=request.url.path,
                detail=f"Non-owner account '{user.username}' attempted owner endpoint access.",
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner administrator privileges required.",
        )
    return user


def assert_resource_ownership(
    resource_user_id: Optional[str],
    current_user: Optional[User],
    resource_name: str = "resource",
) -> None:
    """Enforce strict isolation between authenticated users and guest sessions."""
    caller_uid = current_user.id if current_user else None
    if resource_user_id != caller_uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have permission to access this {resource_name}.",
        )
