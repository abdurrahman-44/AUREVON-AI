from typing import List
from fastapi import APIRouter
from backend.app.schemas.model import ModelInfo, ProviderHealth
from backend.app.services.ai.factory import get_ai_provider

router = APIRouter(prefix="/models", tags=["Models"])


@router.get("", response_model=List[ModelInfo])
async def list_models():
    provider = get_ai_provider("ollama")
    models = await provider.list_models()
    return models


@router.get("/health", response_model=ProviderHealth)
async def check_provider_health():
    provider = get_ai_provider("ollama")
    return await provider.check_health()
