import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.core.config import settings
from backend.app.database.session import init_db
from backend.app.api.routes import health, conversations, chat, models, auth, settings as user_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aurevon.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure database schema and tables are created
    logger.info("Initializing AUREVON AI backend...")
    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Error during database startup: {e}")
    yield
    # Shutdown
    logger.info("AUREVON AI backend shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    description="Independent, open-source-first, multimodal AI assistant platform API.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(user_settings.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(models.router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "status": "online",
        "version": "0.1.0",
        "docs": "/docs",
        "description": "Unified AI assistant platform with model independence.",
    }
