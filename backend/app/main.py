import logging
import time
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.core.config import settings
from backend.app.core.logging import configure_logging
from backend.app.core.security import decode_access_token
from backend.app.database.session import AsyncSessionLocal, get_db, init_db
from backend.app.models.entities import APIRequestLog
from backend.app.services.audit import extract_client_ip
from backend.app.services.intelligence import IntelligenceCoreService
from backend.app.services.platform_settings import PlatformSettingsService
from backend.app.api.routes import (
    health,
    conversations,
    chat,
    models,
    auth,
    admin,
    intelligence,
    settings as user_settings,
    documents,
    memory,
    research,
    agents,
)

# Configure structured logging & error ring buffer
configure_logging(settings.DEBUG)
logger = logging.getLogger("aurevon.main")

_MAINTENANCE_EXEMPT_PREFIXES = (
    "/api/health",
    "/api/admin",
    "/api/auth/admin-login",
    "/api/auth/me",
    "/api/auth/logout",
    "/api/auth/bootstrap-status",
    "/api/auth/bootstrap-owner",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure database schema and tables are created cleanly without deleting user rows
    logger.info("Initializing AUREVON AI backend...")
    try:
        await init_db()
        async with AsyncSessionLocal() as session:
            await IntelligenceCoreService.ensure_initialized(session)
            pcfg = await PlatformSettingsService.ensure_initialized(session)
            settings.RATE_LIMIT_AUTH_PER_MINUTE = pcfg.auth_rate_limit_per_min
            settings.RATE_LIMIT_CHAT_PER_MINUTE = pcfg.chat_rate_limit_per_min
            settings.RATE_LIMIT_UPLOAD_PER_MINUTE = pcfg.upload_rate_limit_per_min
        logger.info("Database, Intelligence Core, and Platform Config initialized successfully.")
    except Exception as e:
        logger.error(f"Error during database startup: {e}")
    yield
    logger.info("AUREVON AI backend shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    description="Independent, open-source-first, multimodal AI assistant platform API.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
)


@app.exception_handler(Exception)
async def safe_unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {type(exc).__name__}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."},
    )


async def _open_telemetry_session(fastapi_app: FastAPI):
    override = fastapi_app.dependency_overrides.get(get_db)
    if override is not None:
        gen = override()
        session = await gen.__anext__()
        return session, gen
    ctx = AsyncSessionLocal()
    session = await ctx.__aenter__()
    return session, ctx


async def _close_telemetry_session(gen_or_ctx, exc=None):
    if hasattr(gen_or_ctx, "aclose"):
        await gen_or_ctx.aclose()
    elif hasattr(gen_or_ctx, "__aexit__"):
        await gen_or_ctx.__aexit__(type(exc) if exc else None, exc, None)


def _extract_user_id_from_auth_header(request: Request) -> Optional[str]:
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header[7:].strip()
    if not token:
        return None
    payload = decode_access_token(token)
    if payload and payload.get("sub"):
        return str(payload["sub"])[:36]
    return None


@app.middleware("http")
async def control_centre_telemetry_and_maintenance_middleware(request: Request, call_next):
    path = request.url.path
    if request.method == "OPTIONS" or not path.startswith("/api/"):
        return await call_next(request)

    started = time.perf_counter()
    snap = None
    try:
        db_session, handle = await _open_telemetry_session(request.app)
        try:
            snap = await PlatformSettingsService.get_snapshot(db_session)
        finally:
            await _close_telemetry_session(handle)
    except Exception:
        snap = None

    if (
        snap
        and snap.get("maintenance_mode")
        and not any(path.startswith(prefix) for prefix in _MAINTENANCE_EXEMPT_PREFIXES)
    ):
        return JSONResponse(
            status_code=503,
            content={
                "detail": snap.get("maintenance_message")
                or "AUREVON AI is currently undergoing scheduled maintenance.",
                "maintenance_mode": True,
            },
        )

    response = await call_next(request)

    if snap is None or snap.get("enable_api_request_logging", True):
        duration_ms = max(1, int((time.perf_counter() - started) * 1000))
        try:
            db_session, handle = await _open_telemetry_session(request.app)
            try:
                log_entry = APIRequestLog(
                    method=request.method[:16],
                    path=path[:255],
                    status_code=int(response.status_code),
                    duration_ms=duration_ms,
                    user_id=_extract_user_id_from_auth_header(request),
                    client_ip=extract_client_ip(request),
                )
                db_session.add(log_entry)
                await db_session.commit()
            finally:
                await _close_telemetry_session(handle)
        except Exception:
            pass

    return response


# CORS Middleware registered after http middleware so it wraps 503/errors properly
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Register API Routers
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(intelligence.router, prefix="/api")
app.include_router(user_settings.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(memory.router, prefix="/api")
app.include_router(research.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(models.router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "status": "online",
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.ENABLE_DOCS else None,
        "description": "Unified AI assistant platform with centralized intelligence control.",
    }
