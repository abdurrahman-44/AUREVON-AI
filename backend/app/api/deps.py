from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database.session import get_db
from backend.app.core.security import decode_access_token
from backend.app.repositories.user_repo import UserRepository
from backend.app.models.entities import User

security_scheme = HTTPBearer(auto_error=False)


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Retrieve user from JWT bearer token if present, otherwise None."""
    if not credentials or not credentials.credentials:
        return None

    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        return None

    user_id = payload["sub"]
    user_repo = UserRepository(db)
    return await user_repo.get_by_id(user_id)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require valid authenticated user."""
    user = await get_optional_user(credentials, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required or token expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
