import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.api.deps import assert_resource_ownership, get_optional_user
from backend.app.core.config import settings
from backend.app.core.rate_limit import rate_limit_dependency
from backend.app.database.session import AsyncSessionLocal, get_db
from backend.app.models.entities import AIRequestLog, Document, Memory, User
from backend.app.repositories.conversation_repo import ConversationRepository
from backend.app.repositories.message_repo import MessageRepository
from backend.app.schemas.chat import ChatRequest
from backend.app.services.ai.base import invoke_provider_stream
from backend.app.services.ai.factory import get_ai_provider
from backend.app.services.ai.model_manager import ModelManager
from backend.app.services.ai.router import RequestRouter
from backend.app.services.documents.rag import RAGService
from backend.app.services.intelligence import IntelligenceCoreService
from backend.app.services.memory.manager import MemoryManager
from backend.app.services.memory.summarizer import ConversationSummarizer
from backend.app.services.tools.executor import ToolExecutor
from backend.app.services.tools.registry import ToolRegistry

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


def _format_tool_observations(records: List[Dict[str, Any]]) -> str:
    if not records:
        return ""
    blocks = ["### Verified Tool Outputs (Ground Truth Results — Use Directly & Accurately):"]
    for rec in records:
        tool_name = rec.get("tool", "tool")
        clean_copy = {k: v for k, v in rec.items() if k != "charts"}
        blocks.append(f"[{tool_name}]: {json.dumps(clean_copy, ensure_ascii=False)}")
    return "\n".join(blocks)


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
    is_new_conversation = False
    if payload.conversation_id:
        conversation = await conv_repo.get_by_id(payload.conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        assert_resource_ownership(conversation.user_id, current_user, "conversation")
    else:
        title = generate_title_from_prompt(payload.message)
        conversation = await conv_repo.create(title=title, user_id=user_id)
        is_new_conversation = True

    conversation_id = conversation.id

    # Centralized AUREVON Intelligence Core: enforces server-side config & active prompt
    runtime = await IntelligenceCoreService.resolve_runtime_settings(
        db=db,
        requested_model=payload.model,
        requested_temperature=payload.temperature,
    )
    sys_config = runtime["config"]
    target_provider = runtime["provider"]
    target_model = runtime["model"]
    target_ctx = runtime["context_window"]
    target_max_tokens = runtime["max_output_tokens"]
    target_keep_alive = runtime["keep_alive"]
    target_keep_alive_secs = runtime["keep_alive_seconds"]
    target_timeout = runtime["request_timeout_seconds"]
    target_temp = runtime["temperature"]
    master_prompt = runtime["master_prompt"]

    # Regeneration handling: clean trailing assistant message & avoid duplicating user turn
    reused_user_msg = None
    if payload.regenerate and not is_new_conversation:
        recent = await msg_repo.get_messages_for_conversation(conversation_id, limit=4)
        if recent and recent[-1].role == "assistant":
            await msg_repo.delete_message(conversation_id, recent[-1].id)
            recent = recent[:-1]
        if recent and recent[-1].role == "user" and recent[-1].content.strip() == payload.message.strip():
            reused_user_msg = recent[-1]

    # Cheap scalar existence checks before routing
    doc_cnt_stmt = select(func.count(Document.id)).where(Document.processing_status == "completed")
    mem_cnt_stmt = select(func.count(Memory.id)).where(Memory.is_active == True)
    if user_id is not None:
        doc_cnt_stmt = doc_cnt_stmt.where(Document.user_id == user_id)
        mem_cnt_stmt = mem_cnt_stmt.where(Memory.user_id == user_id)
    else:
        doc_cnt_stmt = doc_cnt_stmt.where(Document.user_id.is_(None))
        mem_cnt_stmt = mem_cnt_stmt.where(Memory.user_id.is_(None))

    has_documents = bool(payload.document_ids) or int((await db.execute(doc_cnt_stmt)).scalar() or 0) > 0
    has_memories = int((await db.execute(mem_cnt_stmt)).scalar() or 0) > 0

    decision = RequestRouter.classify(
        payload.message,
        document_ids=payload.document_ids,
        web_search=payload.web_search,
        has_documents=has_documents,
        has_memories=has_memories,
    )

    # Persist user message immediately (unless regenerating exact trailing user turn)
    if reused_user_msg is not None:
        user_msg = reused_user_msg
    else:
        user_msg = await msg_repo.create(
            conversation_id=conversation_id,
            role="user",
            content=payload.message,
            model=target_model,
            intent=decision.intent,
        )

    # Post-stream persistence session factory
    session_factory = (
        async_sessionmaker(bind=db.bind, class_=AsyncSession, expire_on_commit=False)
        if db.bind is not None
        else AsyncSessionLocal
    )

    # ULTRA-FAST GREETING PATH (<20ms total, 0 LLM/RAG/Memory wait)
    if decision.use_fast_greeting and decision.fast_greeting_reply and not payload.images and not payload.regenerate:
        fast_reply = decision.fast_greeting_reply

        async def fast_greeting_stream() -> AsyncGenerator[str, None]:
            req_start = time.perf_counter()
            yield f"data: {json.dumps({'conversation_id': conversation_id, 'user_message_id': user_msg.id, 'delta': '', 'done': False, 'model': target_model, 'provider': target_provider, 'model_pinned': runtime['model_pinned'], 'intent': 'greeting'})}\n\n"
            yield f"data: {json.dumps({'conversation_id': conversation_id, 'delta': fast_reply, 'done': False})}\n\n"
            duration_ms = max(1, int((time.perf_counter() - req_start) * 1000))
            assistant_msg_id = None
            try:
                async with session_factory() as post_session:
                    post_msg_repo = MessageRepository(post_session)
                    post_conv_repo = ConversationRepository(post_session)
                    saved_msg = await post_msg_repo.create(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=fast_reply,
                        model=target_model,
                        intent="greeting",
                    )
                    assistant_msg_id = saved_msg.id
                    await post_conv_repo.touch(conversation_id)
                    if user_id:
                        await post_session.execute(
                            update(User).where(User.id == user_id).values(last_active_at=datetime.now(timezone.utc))
                        )
                    post_session.add(
                        AIRequestLog(
                            user_id=user_id,
                            conversation_id=conversation_id,
                            request_type="chat",
                            provider=target_provider,
                            model=target_model,
                            intent="greeting",
                            created_at=datetime.now(timezone.utc),
                            duration_ms=duration_ms,
                            first_token_ms=duration_ms,
                            success=True,
                        )
                    )
                    await post_session.commit()
            except Exception as exc:
                logger.warning(f"Fast greeting telemetry warning: {exc}")

            yield f"data: {json.dumps({'conversation_id': conversation_id, 'assistant_message_id': assistant_msg_id, 'delta': '', 'done': True, 'model': target_model, 'provider': target_provider, 'intent': 'greeting'})}\n\n"

        return StreamingResponse(
            fast_greeting_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    # Select final route model (specialist/cloud consent checks)
    target_provider, target_model, route_note = await ModelManager.select_route_model(
        sys_config,
        target_provider,
        target_model,
        decision.intent,
        payload.allow_cloud,
        db,
        user_id=user_id,
    )

    # Build bounded conversation history + optional rolling summary
    history_messages = await msg_repo.get_messages_for_conversation(
        conversation_id,
        limit=decision.max_history_turns,
    )
    messages_payload: List[Dict[str, Any]] = [{"role": m.role, "content": m.content} for m in history_messages]

    # Context enrichment (only run what RequestRouter indicates)
    if decision.compact_system_prompt:
        system_sections = [
            "You are AUREVON AI, a calm, concise, intellectually honest assistant. Present verified results clearly and never invent missing facts."
        ]
    else:
        system_sections = [master_prompt]

    if not is_new_conversation:
        try:
            rolling_summary = await ConversationSummarizer.get_or_update_summary(db, conversation_id)
            if rolling_summary:
                system_sections.append(f"### Earlier Conversation Summary:\n{rolling_summary}")
        except Exception as exc:
            logger.warning(f"Summary skipped: {exc}")

    user_memory_enabled = True
    if current_user and current_user.settings is not None:
        user_memory_enabled = bool(current_user.settings.memory_enabled)

    # Explicit consent memory saving ("Remember that...")
    saved_memory_notice = None
    if sys_config.enable_memory_injection and user_memory_enabled:
        explicit_mem = MemoryManager.detect_explicit_memory_request(payload.message)
        if explicit_mem:
            fact_text, fact_cat = explicit_mem
            saved_mem = await MemoryManager.save_explicit_memory(db, user_id, fact_text, category=fact_cat)
            if saved_mem:
                saved_memory_notice = f"User explicitly asked to save this memory and it is now stored: [{saved_mem.category}] {saved_mem.content}"
                system_sections.append(saved_memory_notice)

    if decision.needs_memory and sys_config.enable_memory_injection and user_memory_enabled and has_memories:
        try:
            memories = await MemoryManager.get_relevant_memories(db, payload.message, user_id=user_id)
            if memories:
                system_sections.append(MemoryManager.format_memory_context(memories))
        except Exception as e:
            logger.warning(f"Memory retrieval notice: {e}")

    citations: List[Dict[str, Any]] = []
    if decision.needs_rag and sys_config.enable_rag_injection and has_documents:
        try:
            rag_chunks = await RAGService.retrieve_relevant_chunks(
                db,
                payload.message,
                user_id=user_id,
                top_k=4,
                document_ids=payload.document_ids,
            )
            if rag_chunks:
                system_sections.append(RAGService.format_grounded_context(rag_chunks))
                for c in rag_chunks:
                    citations.append(
                        {
                            "source_type": "document",
                            "document_id": c["document_id"],
                            "filename": c["filename"],
                            "page_number": c.get("page_number"),
                            "similarity": c["similarity"],
                            "snippet": c["content"][:220],
                        }
                    )
        except Exception as e:
            logger.warning(f"RAG retrieval notice: {e}")

    # Proactive verified tool execution (Calculator, Date/Time, Python Sandbox, Web Search)
    proactive_tools, web_citations = await ToolExecutor.run_proactive_tools(
        db,
        prompt=payload.message,
        intent=decision.intent,
        suggested_tools=decision.suggested_tools,
        ai_config=sys_config,
        current_user=current_user,
        conversation_id=conversation_id,
        web_search_requested=payload.web_search,
        attached_document_ids=payload.document_ids,
    )
    citations.extend(web_citations)

    svg_charts: List[str] = []
    for rec in proactive_tools:
        if rec.get("charts"):
            svg_charts.extend(rec["charts"])

    if proactive_tools:
        system_sections.append(_format_tool_observations(proactive_tools))
        if any(r.get("tool") == "web_search" and not r.get("ok") for r in proactive_tools):
            system_sections.append(
                "IMPORTANT: Web search did not succeed (either disabled in Control Centre or offline). Explicitly disclose this limitation instead of inventing live facts or URLs."
            )

    if route_note and route_note.endswith("_using_local"):
        system_sections.append(
            f"Note: Cloud inference was bypassed ({route_note}); responding safely on local model `{target_model}`."
        )

    # Describe additional reactive tools ONLY for complex non-compact queries
    if sys_config.enable_agent_tools and not decision.compact_system_prompt:
        system_sections.append(
            ToolRegistry.describe_tools_for_prompt(
                [
                    "calculator",
                    "date_time",
                    "weather",
                    "currency_converter",
                    "news_search",
                    "knowledge_retrieval",
                    "document_reader",
                    "python_data_analysis",
                    "web_search",
                ]
            )
        )

    messages_payload.insert(0, {"role": "system", "content": "\n\n".join(system_sections)})

    # Multimodal image handling & capability check
    has_images = bool(payload.images and len(payload.images) > 0)
    vision_supported = check_model_vision_capability(target_model)

    if has_images and vision_supported:
        if target_provider == "ollama":
            messages_payload[-1]["images"] = payload.images
        else:
            content_blocks: List[Dict[str, Any]] = [{"type": "text", "text": payload.message}]
            for img in payload.images:
                url = img if img.startswith("data:") else f"data:image/jpeg;base64,{img}"
                content_blocks.append({"type": "image_url", "image_url": {"url": url}})
            messages_payload[-1]["content"] = content_blocks

    async def sse_event_stream() -> AsyncGenerator[str, None]:
        req_start = time.perf_counter()
        first_token_ms: Optional[int] = None
        prompt_tokens: Optional[int] = None
        completion_tokens: Optional[int] = None
        total_tokens: Optional[int] = None
        success = True
        interrupted = False
        error_category: Optional[str] = None
        error_message: Optional[str] = None
        used_provider = target_provider
        used_model = target_model
        all_tool_records: List[Dict[str, Any]] = list(proactive_tools)
        accumulated_text: List[str] = []

        init_event = {
            "conversation_id": conversation_id,
            "user_message_id": user_msg.id,
            "delta": "",
            "done": False,
            "model": target_model,
            "provider": target_provider,
            "model_pinned": runtime["model_pinned"],
            "intent": decision.intent,
            "route_note": route_note,
        }
        yield f"data: {json.dumps(init_event)}\n\n"

        for rec in proactive_tools:
            yield f"data: {json.dumps({'conversation_id': conversation_id, 'delta': '', 'done': False, 'tool_event': {k: v for k, v in rec.items() if k != 'charts'}})}\n\n"
        if citations:
            yield f"data: {json.dumps({'conversation_id': conversation_id, 'delta': '', 'done': False, 'citations': citations})}\n\n"
        if svg_charts:
            yield f"data: {json.dumps({'conversation_id': conversation_id, 'delta': '', 'done': False, 'charts': svg_charts})}\n\n"

        if has_images and not vision_supported:
            warning_msg = (
                f"**Model Capability Notice**: The active model `{target_model}` does not support image analysis. "
                f"Multimodal vision requires a vision-compatible model such as `llava:7b`, `qwen2-vl`, or `gpt-4o`."
            )
            yield f"data: {json.dumps({'conversation_id': conversation_id, 'delta': warning_msg, 'done': False})}\n\n"
            yield f"data: {json.dumps({'conversation_id': conversation_id, 'delta': '', 'done': True, 'model': target_model})}\n\n"
            return

        yield f"data: {json.dumps({'conversation_id': conversation_id, 'delta': '', 'done': False, 'status': 'generating'})}\n\n"

        candidates = [(target_provider, target_model)]
        if (
            sys_config.fallback_provider
            and sys_config.fallback_model
            and (sys_config.fallback_provider != target_provider or sys_config.fallback_model != target_model)
        ):
            candidates.append((sys_config.fallback_provider, sys_config.fallback_model))

        try:
            await ModelManager.warm_model_if_needed(
                target_provider,
                target_model,
                target_ctx,
                target_keep_alive_secs,
            )

            working_messages = list(messages_payload)
            max_tool_loops = max(1, min(3, settings.MAX_TOOL_ITERATIONS))
            executed_signatures = set()

            for loop_idx in range(max_tool_loops):
                pass_text: List[str] = []
                pass_succeeded = False

                for idx, (cand_provider_name, cand_model) in enumerate(candidates):
                    used_provider = cand_provider_name
                    used_model = cand_model
                    cand_provider = get_ai_provider(cand_provider_name)
                    cand_error = None
                    pass_text.clear()

                    async for ev in invoke_provider_stream(
                        cand_provider,
                        messages=working_messages,
                        model=cand_model,
                        temperature=target_temp,
                        context_window=target_ctx,
                        max_tokens=target_max_tokens,
                        keep_alive=target_keep_alive,
                        request_timeout=target_timeout,
                    ):
                        etype = ev.get("type")
                        if etype == "token":
                            if first_token_ms is None:
                                first_token_ms = int((time.perf_counter() - req_start) * 1000)
                            text_piece = ev["text"]
                            pass_text.append(text_piece)
                            accumulated_text.append(text_piece)
                            yield f"data: {json.dumps({'conversation_id': conversation_id, 'delta': text_piece, 'done': False})}\n\n"
                        elif etype == "done":
                            prompt_tokens = (prompt_tokens or 0) + (ev.get("prompt_tokens") or 0) if ev.get("prompt_tokens") is not None else prompt_tokens
                            completion_tokens = (completion_tokens or 0) + (ev.get("completion_tokens") or 0) if ev.get("completion_tokens") is not None else completion_tokens
                            total_tokens = ev.get("total_tokens")
                        elif etype == "error":
                            cand_error = ev
                            break

                    if not cand_error:
                        pass_succeeded = True
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

                if not pass_succeeded or not sys_config.enable_agent_tools:
                    break

                raw_pass = "".join(pass_text)
                requested_calls = ToolExecutor.parse_tool_calls(raw_pass)
                if not requested_calls or loop_idx + 1 >= max_tool_loops:
                    break

                # Execute reactive tool calls requested by the model cleanly
                reactive_results = []
                async with session_factory() as tool_session:
                    call_counts: Dict[str, int] = {}
                    for tc in requested_calls[:2]:
                        sig = f"{tc['name']}:{json.dumps(tc['arguments'], sort_keys=True)}"
                        if sig in executed_signatures:
                            continue
                        executed_signatures.add(sig)
                        rec = await ToolExecutor.execute_tool(
                            tool_session,
                            tc["name"],
                            tc["arguments"],
                            ai_config=sys_config,
                            current_user=current_user,
                            conversation_id=conversation_id,
                            call_counts=call_counts,
                            web_search_requested=payload.web_search,
                            attached_document_ids=payload.document_ids,
                        )
                        all_tool_records.append(rec)
                        reactive_results.append(rec)
                        if rec.get("charts"):
                            svg_charts.extend(rec["charts"])
                            yield f"data: {json.dumps({'conversation_id': conversation_id, 'delta': '', 'done': False, 'charts': rec['charts']})}\n\n"
                        yield f"data: {json.dumps({'conversation_id': conversation_id, 'delta': '', 'done': False, 'tool_event': {k: v for k, v in rec.items() if k != 'charts'}})}\n\n"

                if not reactive_results:
                    break

                working_messages.append({"role": "assistant", "content": raw_pass})
                working_messages.append(
                    {
                        "role": "system",
                        "content": _format_tool_observations(reactive_results) + "\nNow write the clear final answer using these tool results (do not output another <tool_call>).",
                    }
                )
        except asyncio.CancelledError:
            interrupted = True
            logger.info(f"Client disconnected / cancelled generation for conversation {conversation_id}")
        except Exception as e:
            logger.exception("Unexpected exception during SSE generation")
            success = False
            error_category = "internal_stream_error"
            error_message = str(e)[:200]
            err_text = "\n\n*Stream generation interrupted due to a server error.*"
            accumulated_text.append(err_text)
            yield f"data: {json.dumps({'conversation_id': conversation_id, 'delta': err_text, 'done': False})}\n\n"

        duration_ms = max(1, int((time.perf_counter() - req_start) * 1000))
        cleaned_content = ToolExecutor.strip_tool_call_tags("".join(accumulated_text))
        if interrupted and cleaned_content:
            cleaned_content += "\n\n*[Generation stopped]*"

        if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens

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
        sanitized_tool_records = [
            {k: v for k, v in rec.items() if k != "charts"}
            for rec in all_tool_records
        ] or None

        try:
            async with session_factory() as post_session:
                post_msg_repo = MessageRepository(post_session)
                post_conv_repo = ConversationRepository(post_session)

                saved_msg = await post_msg_repo.create(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=cleaned_content,
                    model=used_model,
                    token_usage=token_usage_meta,
                    tool_calls=sanitized_tool_records,
                    citations=citations or None,
                    intent=decision.intent,
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
                    intent=decision.intent,
                    tools_used=[r.get("tool") for r in all_tool_records] or None,
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
                await ModelManager.record_provider_usage(
                    post_session,
                    provider=used_provider,
                    model=used_model,
                    user_id=user_id,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    consent_granted=payload.allow_cloud,
                    success=success,
                    latency_ms=duration_ms,
                )
        except Exception as e:
            logger.error(f"Failed post-stream database persistence: {e}")

        if not interrupted:
            final_event = {
                "conversation_id": conversation_id,
                "assistant_message_id": assistant_msg_id,
                "delta": "",
                "done": True,
                "model": used_model,
                "provider": used_provider,
                "intent": decision.intent,
                "token_usage": token_usage_meta,
                "citations": citations or None,
                "tools_used": sanitized_tool_records,
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
