import json
import logging
import time
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.api.deps import assert_resource_ownership, get_optional_user
from backend.app.core.config import settings
from backend.app.core.rate_limit import rate_limit_dependency
from backend.app.database.session import AsyncSessionLocal, get_db
from backend.app.models.entities import AIRequestLog, User
from backend.app.repositories.conversation_repo import ConversationRepository
from backend.app.repositories.message_repo import MessageRepository
from backend.app.schemas.chat import ChatRequest
from backend.app.services.ai.factory import get_ai_provider
from backend.app.services.documents.rag import RAGService
from backend.app.services.intelligence import IntelligenceCoreService
from backend.app.services.memory.manager import MemoryManager

logger = logging.getLogger("aurevon.api.chat")
router = APIRouter(prefix="/chat", tags=["Chat"])

_VISION_INDICATORS = ("vision", "vl", "llava", "4o", "gpt-4-turbo", "claude")


def generate_title_from_prompt(prompt: str) -> str:
    cleaned = prompt.strip().replace("\n", " ")
    if len(cleaned) <= 36:
        return cleaned
    return cleaned[:36] + "..."


def check_model_vision_capability(model_name: str) -> bool:
    m = (model_name or "").lower()
    return any(ind in m for ind in _VISION_INDICATORS)


@router.post(
    "",
    dependencies=[Depends(rate_limit_dependency("chat", lambda: settings.RATE_LIMIT_CHAT_PER_MINUTE))],
)
async def chat_endpoint(
    payload: ChatRequest,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    conv_repo = ConversationRepository(db)
    msg_repo = MessageRepository(db)

    user_id = current_user.id if current_user else None
    if payload.conversation_id:
        conversation = await conv_repo.get_by_id(payload.conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        assert_resource_ownership(conversation.user_id, current_user, "conversation")
    else:
        title = generate_title_from_prompt(payload.message)
        conversation = await conv_repo.create(title=title, user_id=user_id)

    conversation_id = conversation.id

    # Centralized AUREVON Intelligence Core: enforces server-side model pinning & master instruction
    runtime = await IntelligenceCoreService.resolve_runtime_settings(
        db=db,
        requested_model=payload.model,
        requested_temperature=payload.temperature,
    )
    target_provider = runtime["provider"]
    target_model = runtime["model"]
    target_ctx = runtime["context_window"]
    target_temp = runtime["temperature"]
    master_prompt = runtime["master_prompt"]
    sys_config = runtime["config"]

    # Persist user message immediately
    user_msg = await msg_repo.create(
        conversation_id=conversation_id,
        role="user",
        content=payload.message,
        model=target_model,
    )

    # Retrieve recent conversation history for model context window (last 20 messages)
    history_messages = await msg_repo.get_messages_for_conversation(conversation_id, limit=20)
    messages_payload = [{"role": m.role, "content": m.content} for m in history_messages]

    # Context Enrichment: Master Prompt + Active Memory + Document RAG
    system_sections = [master_prompt]

    user_memory_enabled = True
    if current_user and current_user.settings is not None:
        user_memory_enabled = bool(current_user.settings.memory_enabled)

    if sys_config.enable_memory_injection and user_memory_enabled:
        try:
            memories = await MemoryManager.get_relevant_memories(db, payload.message, user_id=user_id)
            if memories:
                system_sections.append(MemoryManager.format_memory_context(memories))
        except Exception as e:
            logger.warning(f"Memory retrieval notice: {e}")

    if sys_config.enable_rag_injection:
        try:
            rag_chunks = await RAGService.retrieve_relevant_chunks(db, payload.message, user_id=user_id)
            if rag_chunks:
                system_sections.append(RAGService.format_grounded_context(rag_chunks))
        except Exception as e:
            logger.warning(f"RAG retrieval notice: {e}")

    messages_payload.insert(0, {"role": "system", "content": "\n\n".join(system_sections)})

    # Multimodal image handling & capability check
    has_images = bool(payload.images and len(payload.images) > 0)
    vision_supported = check_model_vision_capability(target_model)

    if has_images and vision_supported:
        if target_provider == "ollama":
            messages_payload[-1]["images"] = payload.images
        else:
            content_blocks = [{"type": "text", "text": payload.message}]
            for img in payload.images:
                url = img if img.startswith("data:") else f"data:image/jpeg;base64,{img}"
                content_blocks.append({"type": "image_url", "image_url": {"url": url}})
            messages_payload[-1]["content"] = content_blocks

    # Ensure post-stream persistence writes to the active engine (respecting test DB overrides)
    session_factory = (
        async_sessionmaker(bind=db.bind, class_=AsyncSession, expire_on_commit=False)
        if db.bind is not None
        else AsyncSessionLocal
    )

    async def sse_event_stream() -> AsyncGenerator[str, None]:
        req_start = time.perf_counter()
        first_token_ms: Optional[int] = None
        prompt_tokens: Optional[int] = None
        completion_tokens: Optional[int] = None
        total_tokens: Optional[int] = None
        success = True
        error_category: Optional[str] = None
        error_message: Optional[str] = None
        used_provider = target_provider
        used_model = target_model

        init_event = {
            "conversation_id": conversation_id,
            "user_message_id": user_msg.id,
            "delta": "",
            "done": False,
            "model": target_model,
            "provider": target_provider,
            "model_pinned": runtime["model_pinned"],
        }
        yield f"data: {json.dumps(init_event)}\n\n"

        if has_images and not vision_supported:
            warning_msg = (
                f"⚠️ **Model Capability Notice**: The active model `{target_model}` does not support image analysis. "
                f"Multimodal vision requires a vision-compatible model such as `llava:7b`, `qwen2-vl`, or `gpt-4o`."
            )
            yield f"data: {json.dumps({'conversation_id': conversation_id, 'delta': warning_msg, 'done': False})}\n\n"
            yield f"data: {json.dumps({'conversation_id': conversation_id, 'delta': '', 'done': True, 'model': target_model})}\n\n"
            return

        accumulated_text = []
        candidates = [(target_provider, target_model)]
        if (
            sys_config.fallback_provider
            and sys_config.fallback_model
            and (sys_config.fallback_provider != target_provider or sys_config.fallback_model != target_model)
        ):
            candidates.append((sys_config.fallback_provider, sys_config.fallback_model))

        try:
            for idx, (cand_provider_name, cand_model) in enumerate(candidates):
                used_provider = cand_provider_name
                used_model = cand_model
                cand_provider = get_ai_provider(cand_provider_name)
                cand_error = None

                async for ev in cand_provider.stream_chat_with_metrics(
                    messages=messages_payload,
                    model=cand_model,
                    temperature=target_temp,
                    context_window=target_ctx,
                ):
                    etype = ev.get("type")
                    if etype == "token":
                        if first_token_ms is None:
                            first_token_ms = int((time.perf_counter() - req_start) * 1000)
                        text_piece = ev["text"]
                        accumulated_text.append(text_piece)
                        yield f"data: {json.dumps({'conversation_id': conversation_id, 'delta': text_piece, 'done': False})}\n\n"
                    elif etype == "done":
                        prompt_tokens = ev.get("prompt_tokens")
                        completion_tokens = ev.get("completion_tokens")
                        total_tokens = ev.get("total_tokens")
                    elif etype == "error":
                        cand_error = ev
                        break

                if not cand_error:
                    break

                has_next_fallback = (idx + 1 < len(candidates)) and (not accumulated_text)
                if has_next_fallback:
                    logger.warning(
                        f"Primary provider {cand_provider_name}/{cand_model} failed ({cand_error.get('error_category')}); "
                        f"failing over to {candidates[idx + 1][0]}/{candidates[idx + 1][1]}."
                    )
                    continue

                success = False
                error_category = cand_error.get("error_category", "provider_error")
                error_message = cand_error.get("error_message", "Provider error")
                u_msg = cand_error.get("user_message", "\n\n**Provider Error**: Unable to complete request.")
                accumulated_text.append(u_msg)
                yield f"data: {json.dumps({'conversation_id': conversation_id, 'delta': u_msg, 'done': False})}\n\n"
                break
        except Exception as e:
            logger.exception("Unexpected exception during SSE generation")
            success = False
            error_category = "internal_stream_error"
            error_message = str(e)[:200]
            err_text = "\n\n*Stream generation interrupted due to a server error.*"
            accumulated_text.append(err_text)
            yield f"data: {json.dumps({'conversation_id': conversation_id, 'delta': err_text, 'done': False})}\n\n"

        duration_ms = max(1, int((time.perf_counter() - req_start) * 1000))
        full_content = "".join(accumulated_text)

        assistant_msg_id = None
        token_usage_meta = (
            {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
            if total_tokens is not None or prompt_tokens is not None or completion_tokens is not None
            else None
        )

        # Persist assistant message, update user activity, and log operational AI telemetry
        try:
            async with session_factory() as post_session:
                post_msg_repo = MessageRepository(post_session)
                post_conv_repo = ConversationRepository(post_session)

                saved_msg = await post_msg_repo.create(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=full_content,
                    model=used_model,
                    token_usage=token_usage_meta,
                )
                assistant_msg_id = saved_msg.id
                await post_conv_repo.touch(conversation_id)

                if user_id:
                    await post_session.execute(
                        update(User).where(User.id == user_id).values(last_active_at=datetime.now(timezone.utc))
                    )

                log_entry = AIRequestLog(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    request_type="chat",
                    provider=used_provider,
                    model=used_model,
                    created_at=datetime.now(timezone.utc),
                    duration_ms=duration_ms,
                    first_token_ms=first_token_ms,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    success=success,
                    error_category=error_category,
                    error_message=error_message[:255] if error_message else None,
                )
                post_session.add(log_entry)
                await post_session.commit()
        except Exception as e:
            logger.error(f"Failed post-stream database persistence: {e}")

        final_event = {
            "conversation_id": conversation_id,
            "assistant_message_id": assistant_msg_id,
            "delta": "",
            "done": True,
            "model": used_model,
            "provider": used_provider,
            "token_usage": token_usage_meta,
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
