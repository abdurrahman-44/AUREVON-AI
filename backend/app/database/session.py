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


async def _sqlite_add_column_if_missing(
    conn: AsyncConnection,
    table: str,
    column: str,
    ddl: str,
) -> None:
    res = await conn.execute(text(f"PRAGMA table_info({table})"))
    existing_cols = {row[1] for row in res.fetchall()}
    if column not in existing_cols:
        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


async def _ensure_sqlite_fts5(conn: AsyncConnection) -> None:
    """Create and backfill SQLite FTS5 index for document chunks if FTS5 is compiled in."""
    try:
        await conn.execute(
            text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts "
                "USING fts5(chunk_id UNINDEXED, document_id UNINDEXED, content, tokenize='porter unicode61')"
            )
        )
        # Backfill any chunks missing from the FTS index (idempotent & incremental)
        await conn.execute(
            text(
                "INSERT INTO document_chunks_fts(chunk_id, document_id, content) "
                "SELECT dc.id, dc.document_id, dc.content FROM document_chunks dc "
                "WHERE NOT EXISTS (SELECT 1 FROM document_chunks_fts f WHERE f.chunk_id = dc.id)"
            )
        )
    except Exception as exc:
        logger.warning(f"SQLite FTS5 initialization skipped (fallback keyword scoring active): {exc}")


async def _apply_v2_column_upgrades(conn: AsyncConnection) -> None:
    """Safely upgrade existing v1/v2 tables in-place without losing user rows."""
    dialect = conn.dialect.name
    if dialect == "sqlite":
        await _sqlite_add_column_if_missing(conn, "users", "role", "VARCHAR(32) NOT NULL DEFAULT 'user'")
        await _sqlite_add_column_if_missing(conn, "users", "is_active", "BOOLEAN NOT NULL DEFAULT 1")
        await _sqlite_add_column_if_missing(conn, "users", "last_active_at", "DATETIME")
        await _sqlite_add_column_if_missing(conn, "users", "totp_secret", "VARCHAR(64)")
        await _sqlite_add_column_if_missing(conn, "users", "totp_enabled", "BOOLEAN NOT NULL DEFAULT 0")
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_is_active ON users (is_active)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_last_active_at ON users (last_active_at)"))

        # Intelligence Engine additive columns
        await _sqlite_add_column_if_missing(conn, "messages", "tool_calls", "JSON")
        await _sqlite_add_column_if_missing(conn, "messages", "citations", "JSON")
        await _sqlite_add_column_if_missing(conn, "messages", "intent", "VARCHAR(64)")

        await _sqlite_add_column_if_missing(conn, "documents", "content_hash", "VARCHAR(64)")
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_content_hash ON documents (content_hash)"))

        await _sqlite_add_column_if_missing(conn, "ai_request_logs", "intent", "VARCHAR(64)")
        await _sqlite_add_column_if_missing(conn, "ai_request_logs", "tools_used", "JSON")
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ai_request_logs_intent ON ai_request_logs (intent)"))

        await _sqlite_add_column_if_missing(conn, "system_ai_configs", "coding_provider", "VARCHAR(64)")
        await _sqlite_add_column_if_missing(conn, "system_ai_configs", "coding_model", "VARCHAR(128)")
        await _sqlite_add_column_if_missing(conn, "system_ai_configs", "max_output_tokens", "INTEGER NOT NULL DEFAULT 2048")
        await _sqlite_add_column_if_missing(conn, "system_ai_configs", "keep_alive_seconds", "INTEGER NOT NULL DEFAULT 900")
        await _sqlite_add_column_if_missing(conn, "system_ai_configs", "request_timeout_seconds", "INTEGER NOT NULL DEFAULT 120")
        await _sqlite_add_column_if_missing(conn, "system_ai_configs", "streaming_enabled", "BOOLEAN NOT NULL DEFAULT 1")
        await _sqlite_add_column_if_missing(conn, "system_ai_configs", "web_search_enabled", "BOOLEAN NOT NULL DEFAULT 0")
        await _sqlite_add_column_if_missing(conn, "system_ai_configs", "cloud_inference_enabled", "BOOLEAN NOT NULL DEFAULT 0")
        await _sqlite_add_column_if_missing(conn, "system_ai_configs", "require_cloud_consent", "BOOLEAN NOT NULL DEFAULT 1")
        await _sqlite_add_column_if_missing(conn, "system_ai_configs", "cloud_daily_limit", "INTEGER NOT NULL DEFAULT 100")

        await _ensure_sqlite_fts5(conn)
    elif dialect == "postgresql":
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(32) NOT NULL DEFAULT 'user'"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMP"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret VARCHAR(64)"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_enabled BOOLEAN NOT NULL DEFAULT FALSE"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_is_active ON users (is_active)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_last_active_at ON users (last_active_at)"))

        await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS tool_calls JSONB"))
        await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS citations JSONB"))
        await conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS intent VARCHAR(64)"))

        await conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_content_hash ON documents (content_hash)"))

        await conn.execute(text("ALTER TABLE ai_request_logs ADD COLUMN IF NOT EXISTS intent VARCHAR(64)"))
        await conn.execute(text("ALTER TABLE ai_request_logs ADD COLUMN IF NOT EXISTS tools_used JSONB"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ai_request_logs_intent ON ai_request_logs (intent)"))

        await conn.execute(text("ALTER TABLE system_ai_configs ADD COLUMN IF NOT EXISTS coding_provider VARCHAR(64)"))
        await conn.execute(text("ALTER TABLE system_ai_configs ADD COLUMN IF NOT EXISTS coding_model VARCHAR(128)"))
        await conn.execute(text("ALTER TABLE system_ai_configs ADD COLUMN IF NOT EXISTS max_output_tokens INTEGER NOT NULL DEFAULT 2048"))
        await conn.execute(text("ALTER TABLE system_ai_configs ADD COLUMN IF NOT EXISTS keep_alive_seconds INTEGER NOT NULL DEFAULT 900"))
        await conn.execute(text("ALTER TABLE system_ai_configs ADD COLUMN IF NOT EXISTS request_timeout_seconds INTEGER NOT NULL DEFAULT 120"))
        await conn.execute(text("ALTER TABLE system_ai_configs ADD COLUMN IF NOT EXISTS streaming_enabled BOOLEAN NOT NULL DEFAULT TRUE"))
        await conn.execute(text("ALTER TABLE system_ai_configs ADD COLUMN IF NOT EXISTS web_search_enabled BOOLEAN NOT NULL DEFAULT FALSE"))
        await conn.execute(text("ALTER TABLE system_ai_configs ADD COLUMN IF NOT EXISTS cloud_inference_enabled BOOLEAN NOT NULL DEFAULT FALSE"))
        await conn.execute(text("ALTER TABLE system_ai_configs ADD COLUMN IF NOT EXISTS require_cloud_consent BOOLEAN NOT NULL DEFAULT TRUE"))
        await conn.execute(text("ALTER TABLE system_ai_configs ADD COLUMN IF NOT EXISTS cloud_daily_limit INTEGER NOT NULL DEFAULT 100"))


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
