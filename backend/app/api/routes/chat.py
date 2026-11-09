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

    # Ensure provider is instantiated
    provider = get_ai_provider("ollama")

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
