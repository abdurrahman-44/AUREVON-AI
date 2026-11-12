import logging
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from backend.app.core.config import settings

logger = logging.getLogger("aurevon.database")

Base = declarative_base()


def get_async_database_url(url: str) -> str:
    """Normalize database URL for async drivers."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


db_url = get_async_database_url(settings.DATABASE_URL)

engine_kwargs = {}
if "sqlite" in db_url:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_async_engine(
    db_url,
    echo=settings.DEBUG and False,
    future=True,
    **engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing database sessions to API routes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def _apply_v2_column_upgrades(conn: AsyncConnection) -> None:
    """Safely upgrade existing v1 tables in-place without losing user rows."""
    dialect = conn.dialect.name
    if dialect == "sqlite":
        res = await conn.execute(text("PRAGMA table_info(users)"))
        existing_cols = {row[1] for row in res.fetchall()}
        if "role" not in existing_cols:
            await conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(32) NOT NULL DEFAULT 'user'"))
        if "is_active" not in existing_cols:
            await conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"))
        if "last_active_at" not in existing_cols:
            await conn.execute(text("ALTER TABLE users ADD COLUMN last_active_at DATETIME"))
        if "totp_secret" not in existing_cols:
            await conn.execute(text("ALTER TABLE users ADD COLUMN totp_secret VARCHAR(64)"))
        if "totp_enabled" not in existing_cols:
            await conn.execute(text("ALTER TABLE users ADD COLUMN totp_enabled BOOLEAN NOT NULL DEFAULT 0"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_is_active ON users (is_active)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_last_active_at ON users (last_active_at)"))
    elif dialect == "postgresql":
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(32) NOT NULL DEFAULT 'user'"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMP"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret VARCHAR(64)"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_enabled BOOLEAN NOT NULL DEFAULT FALSE"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_is_active ON users (is_active)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_last_active_at ON users (last_active_at)"))


async def init_db() -> None:
    """Initialize database tables and apply non-destructive schema upgrades."""
    import backend.app.models  # noqa: F401 - register all ORM models on Base.metadata

    try:
        async with engine.begin() as conn:
            # Create all tables defined in models
            await conn.run_sync(Base.metadata.create_all)
            await _apply_v2_column_upgrades(conn)
        logger.info("Database schema initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
        raise e
