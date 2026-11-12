from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db
from backend.app.schemas.admin import PublicIntelligenceResponse
from backend.app.services.intelligence import IntelligenceCoreService

router = APIRouter(prefix="/intelligence", tags=["Intelligence Core"])


@router.get("/public", response_model=PublicIntelligenceResponse)
async def get_public_intelligence_config(db: AsyncSession = Depends(get_db)):
    """Expose non-sensitive centralized AI configuration metadata to the client UI."""
    return await IntelligenceCoreService.get_public_config(db)
