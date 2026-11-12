import json
import httpx
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from backend.app.api.deps import require_admin
from backend.app.models.entities import User
from backend.app.schemas.model import ModelInfo, ProviderHealth
from backend.app.services.ai.factory import ProviderFactory, get_ai_provider
from backend.app.core.config import settings

router = APIRouter(prefix="/models", tags=["Models"])


class ConfigureProviderRequest(BaseModel):
    provider: str = Field(..., description="Provider name: openai, groq, deepseek")
    api_key: str = Field(..., min_length=1, description="API Key for the provider")
    base_url: Optional[str] = None


class PullModelRequest(BaseModel):
    name: str = Field(..., description="Model name to pull in Ollama, e.g. qwen2.5:3b")


@router.get("", response_model=List[ModelInfo])
async def list_models():
    """List all available models from local Ollama and configured cloud providers."""
    all_models = []
    providers = ProviderFactory.list_all_providers()
    
    for provider in providers:
        try:
            p_models = await provider.list_models()
            all_models.extend(p_models)
        except Exception:
            continue

    if not all_models:
        # Guarantee fallback
        ollama = get_ai_provider("ollama")
        all_models = await ollama.list_models()

    return all_models


@router.get("/health", response_model=List[ProviderHealth])
async def check_all_providers_health():
    """Check health across all local and cloud providers."""
    healths = []
    providers = ProviderFactory.list_all_providers()
    for provider in providers:
        h = await provider.check_health()
        healths.append(h)
    return healths


@router.post("/configure")
async def configure_provider(
    payload: ConfigureProviderRequest,
    admin_user: User = Depends(require_admin),
):
    """Securely configure a cloud AI provider API key (Owner only)."""
    p_name = payload.provider.lower()
    ProviderFactory.set_api_key(p_name, payload.api_key)
    provider = ProviderFactory.get_provider(p_name)
    health = await provider.check_health()
    return {
        "status": "configured",
        "provider": p_name,
        "health": health,
    }


@router.post("/pull")
async def pull_model_endpoint(
    payload: PullModelRequest,
    admin_user: User = Depends(require_admin),
):
    """Trigger an Ollama model pull and stream progress via SSE (Owner only)."""
    model_name = payload.name.strip()
    ollama_url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/pull"

    async def stream_pull():
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream("POST", ollama_url, json={"name": model_name}) as resp:
                    if resp.status_code != 200:
                        yield f"data: {json.dumps({'error': f'Ollama pull error: HTTP {resp.status_code}'})}\n\n"
                        return

                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        yield f"data: {line}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        stream_pull(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
