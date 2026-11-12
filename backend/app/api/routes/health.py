from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from backend.app.database.session import get_db
from backend.app.services.ai.factory import get_ai_provider
from backend.app.schemas.model import SystemStatusResponse, ProviderHealth
from backend.app.core.config import settings

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=SystemStatusResponse)
async def get_system_health(db: AsyncSession = Depends(get_db)):
    # 1. Database check
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    # 2. AI Provider check
    provider = get_ai_provider("ollama")
    ollama_health = await provider.check_health()

    return SystemStatusResponse(
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        database=db_status,
        providers=[ollama_health],
    )
