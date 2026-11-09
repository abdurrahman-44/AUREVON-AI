import json
import logging
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db, AsyncSessionLocal
from backend.app.schemas.chat import ChatRequest
from backend.app.repositories.conversation_repo import ConversationRepository
from backend.app.repositories.message_repo import MessageRepository
from backend.app.services.ai.factory import get_ai_provider
from backend.app.services.documents.rag import RAGService
from backend.app.services.memory.manager import MemoryManager
from backend.app.api.deps import get_optional_user
from backend.app.models.entities import User
from backend.app.core.config import settings

logger = logging.getLogger("aurevon.api.chat")
router = APIRouter(prefix="/chat", tags=["Chat"])


def generate_title_from_prompt(prompt: str) -> str:
    cleaned = prompt.strip().replace("\n", " ")
    if len(cleaned) <= 36:
        return cleaned
    return cleaned[:36] + "..."


@router.post("")
async def chat_endpoint(
    payload: ChatRequest,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    conv_repo = ConversationRepository(db)
    msg_repo = MessageRepository(db)

    # 1. Resolve or create conversation
    conversation = None
    user_id = current_user.id if current_user else None
    if payload.conversation_id:
        conversation = await conv_repo.get_by_id(payload.conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        title = generate_title_from_prompt(payload.message)
        conversation = await conv_repo.create(title=title, user_id=user_id)

    conversation_id = conversation.id
    target_model = payload.model or settings.DEFAULT_MODEL

    # 2. Persist user message immediately
    user_msg = await msg_repo.create(
        conversation_id=conversation_id,
        role="user",
        content=payload.message,
        model=target_model,
    )

    # 3. Retrieve recent conversation history for model context window (last 20 messages)
    history_messages = await msg_repo.get_messages_for_conversation(conversation_id, limit=20)
    messages_payload = [
        {"role": m.role, "content": m.content}
        for m in history_messages
    ]

    # 4. Context Enrichment: RAG Document Retrieval & Active Memory
    system_additions = []
    
    # 4a. Check for relevant user memories
    try:
        memories = await MemoryManager.get_relevant_memories(db, payload.message, user_id=user_id)
        if memories:
            system_additions.append(MemoryManager.format_memory_context(memories))
    except Exception as e:
        logger.warning(f"Memory retrieval notice: {e}")

    # 4b. Check for relevant document citations (RAG)
    try:
        rag_chunks = await RAGService.retrieve_relevant_chunks(db, payload.message, user_id=user_id)
        if rag_chunks:
            system_additions.append(RAGService.format_grounded_context(rag_chunks))
    except Exception as e:
        logger.warning(f"RAG retrieval notice: {e}")

    if system_additions:
        enriched_system_msg = {
            "role": "system",
            "content": "You are AUREVON AI. Ground your responses using the following user context:\n\n" + "\n\n".join(system_additions),
        }
        messages_payload.insert(0, enriched_system_msg)

    # Resolve target provider based on model family
    def resolve_provider_for_model(model_name: str) -> str:
        m = model_name.lower()
        if "gpt" in m or "o1" in m or "o3" in m:
            return "openai"
        if "groq" in m or "llama-3.3" in m:
            return "groq"
        if "deepseek" in m:
            return "deepseek"
        return "ollama"

    def check_model_vision_capability(model_name: str) -> bool:
        m = model_name.lower()
        vision_indicators = ["vision", "vl", "llava", "4o", "gpt-4-turbo", "claude"]
        return any(ind in m for ind in vision_indicators)

    provider_name = resolve_provider_for_model(target_model)
    provider = get_ai_provider(provider_name)

    # Multimodal image handling & capability check
    has_images = bool(payload.images and len(payload.images) > 0)
    vision_supported = check_model_vision_capability(target_model)

    if has_images and vision_supported:
        # Attach images to the latest user message
        if provider_name == "ollama":
            messages_payload[-1]["images"] = payload.images
        else:
            # OpenAI / Cloud multimodal block format
            content_blocks = [{"type": "text", "text": payload.message}]
            for img in payload.images:
                url = img if img.startswith("data:") else f"data:image/jpeg;base64,{img}"
                content_blocks.append({"type": "image_url", "image_url": {"url": url}})
            messages_payload[-1]["content"] = content_blocks

    async def sse_event_stream() -> AsyncGenerator[str, None]:
        # Send initial event with conversation ID and user message ID
        init_event = {
            "conversation_id": conversation_id,
            "user_message_id": user_msg.id,
            "delta": "",
            "done": False,
            "model": target_model,
        }
        yield f"data: {json.dumps(init_event)}\n\n"

        # Check vision capability violation:
        if has_images and not vision_supported:
            warning_msg = (
                f"⚠️ **Model Capability Notice**: The selected model `{target_model}` does not support image analysis. "
                f"Multimodal vision requires a vision-compatible model such as `llava:7b`, `qwen2-vl`, or `gpt-4o`. "
                f"Please switch to a vision model to inspect images."
            )
            yield f"data: {json.dumps({'conversation_id': conversation_id, 'delta': warning_msg, 'done': False})}\n\n"
            yield f"data: {json.dumps({'conversation_id': conversation_id, 'delta': '', 'done': True, 'model': target_model})}\n\n"
            return

        accumulated_text = []

        try:
            async for token in provider.stream_chat(
                messages=messages_payload,
                model=target_model,
                temperature=payload.temperature or settings.GENERATION_TEMPERATURE,
                context_window=settings.MODEL_CONTEXT_WINDOW,
            ):
                accumulated_text.append(token)
                chunk_data = {
                    "conversation_id": conversation_id,
                    "delta": token,
                    "done": False,
                }
                yield f"data: {json.dumps(chunk_data)}\n\n"
        except Exception as e:
            logger.exception("Error during provider stream generation")
            err_text = f"\n\n*Stream generation interrupted: {str(e)}*"
            accumulated_text.append(err_text)
            yield f"data: {json.dumps({'conversation_id': conversation_id, 'delta': err_text, 'done': False})}\n\n"

        full_content = "".join(accumulated_text)

        # 4. Save completed assistant message in database with independent session
        assistant_msg_id = None
        try:
            async with AsyncSessionLocal() as post_session:
                post_msg_repo = MessageRepository(post_session)
                post_conv_repo = ConversationRepository(post_session)
                
                saved_msg = await post_msg_repo.create(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=full_content,
                    model=target_model,
                )
                assistant_msg_id = saved_msg.id
                await post_conv_repo.touch(conversation_id)
        except Exception as e:
            logger.error(f"Failed to persist assistant message to database: {e}")

        # Send final completion event
        final_event = {
            "conversation_id": conversation_id,
            "assistant_message_id": assistant_msg_id,
            "delta": "",
            "done": True,
            "model": target_model,
        }
        yield f"data: {json.dumps(final_event)}\n\n"

    return StreamingResponse(
        sse_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
