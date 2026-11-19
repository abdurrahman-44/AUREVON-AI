import asyncio
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models.entities import SystemAIConfig, ToolConfig, ToolExecutionLog, User
from backend.app.services.tools.calculator import CalculatorTool
from backend.app.services.tools.currency_tool import CurrencyTool
from backend.app.services.tools.datetime_tool import DateTimeTool
from backend.app.services.tools.document_reader_tool import DocumentReaderTool
from backend.app.services.tools.knowledge_tool import KnowledgeRetrievalTool
from backend.app.services.tools.news_tool import NewsTool
from backend.app.services.tools.python_sandbox import PythonSandboxTool
from backend.app.services.tools.registry import ToolRegistry
from backend.app.services.tools.weather_tool import WeatherTool
from backend.app.services.tools.web_search_tool import WebSearchTool

_TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
_PY_BLOCK_RE = re.compile(r"```python\s*(.*?)```", re.DOTALL | re.IGNORECASE)


class ToolExecutor:
    """Validates, authorizes, executes, timeouts, and logs AI tool calls cleanly."""

    @classmethod
    def parse_tool_calls(cls, assistant_text: str) -> List[Dict[str, Any]]:
        calls: List[Dict[str, Any]] = []
        for raw_json in _TOOL_CALL_RE.findall(assistant_text or ""):
            try:
                parsed = json.loads(raw_json)
                if isinstance(parsed, dict) and isinstance(parsed.get("name"), str):
                    args = parsed.get("arguments")
                    calls.append(
                        {
                            "name": parsed["name"].strip(),
                            "arguments": args if isinstance(args, dict) else {},
                        }
                    )
            except json.JSONDecodeError:
                continue
        return calls

    @classmethod
    def strip_tool_call_tags(cls, text: str) -> str:
        return _TOOL_CALL_RE.sub("", text or "").strip()

    @classmethod
    def validate_arguments(cls, tool_name: str, arguments: Dict[str, Any]) -> Optional[str]:
        spec = ToolRegistry.get_spec(tool_name)
        if not spec:
            return f"Unknown tool '{tool_name}'"
        schema = spec.get("schema", {})
        for req_key in schema.get("required", []):
            val = arguments.get(req_key)
            if val is None or (isinstance(val, str) and not val.strip()):
                return f"Missing required argument '{req_key}' for tool '{tool_name}'"
        return None

    @classmethod
    async def execute_tool(
        cls,
        db: AsyncSession,
        tool_name: str,
        arguments: Dict[str, Any],
        *,
        ai_config: SystemAIConfig,
        current_user: Optional[User],
        conversation_id: Optional[str] = None,
        call_counts: Optional[Dict[str, int]] = None,
        web_search_requested: bool = False,
        attached_document_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        configs = {c.tool_name: c for c in await ToolRegistry.ensure_seeded(db)}
        t_cfg: Optional[ToolConfig] = configs.get(tool_name)
        user_id = current_user.id if current_user else None

        async def _log_and_return(result: Dict[str, Any], status_val: str, err_msg: Optional[str] = None) -> Dict[str, Any]:
            dur = int((time.perf_counter() - started) * 1000)
            entry = ToolExecutionLog(
                tool_name=tool_name,
                user_id=user_id,
                conversation_id=conversation_id,
                status=status_val,
                duration_ms=dur,
                error_summary=(err_msg or "")[:250] or None,
                created_at=datetime.now(timezone.utc),
            )
            db.add(entry)
            await db.commit()
            return {"tool": tool_name, "duration_ms": dur, "status": status_val, **result}

        if not t_cfg:
            return await _log_and_return({"ok": False, "error": f"Unknown tool '{tool_name}'"}, "blocked", "unknown_tool")

        # Permission & enablement gates
        web_policy_enabled = bool(ai_config.web_search_enabled or t_cfg.is_enabled)
        if tool_name == "web_search":
            if not web_policy_enabled:
                return await _log_and_return(
                    {
                        "ok": False,
                        "status": "disabled_by_policy",
                        "error": "Web search is currently disabled in Control Centre.",
                        "results": [],
                    },
                    "blocked",
                    "disabled_by_policy",
                )
        elif not t_cfg.is_enabled:
            return await _log_and_return(
                {"ok": False, "error": f"Tool '{tool_name}' is disabled by platform policy."},
                "blocked",
                "disabled",
            )

        if t_cfg.permission_level == "disabled":
            return await _log_and_return(
                {"ok": False, "error": f"Tool '{tool_name}' is disabled."},
                "blocked",
                "permission_disabled",
            )
        if t_cfg.permission_level == "owner_only" and (not current_user or current_user.role != "owner"):
            return await _log_and_return(
                {"ok": False, "error": f"Tool '{tool_name}' requires owner authorization."},
                "blocked",
                "owner_only",
            )
        if tool_name not in ("knowledge_retrieval", "document_reader") and not ai_config.enable_agent_tools:
            return await _log_and_return(
                {"ok": False, "error": "Agent tools are currently disabled globally."},
                "blocked",
                "global_tools_disabled",
            )

        if call_counts is not None:
            prior = call_counts.get(tool_name, 0)
            if prior >= int(t_cfg.max_calls_per_request or 3):
                return await _log_and_return(
                    {"ok": False, "error": f"Tool '{tool_name}' exceeded max calls per request."},
                    "blocked",
                    "rate_exceeded",
                )
            call_counts[tool_name] = prior + 1

        validation_err = cls.validate_arguments(tool_name, arguments)
        if validation_err:
            return await _log_and_return({"ok": False, "error": validation_err}, "error", validation_err)

        timeout_s = max(1, min(30, int(t_cfg.timeout_seconds or settings.TOOL_EXECUTION_TIMEOUT_SECONDS)))

        try:
            if tool_name == "calculator":
                res = CalculatorTool.execute(str(arguments.get("expression", "")))
            elif tool_name == "date_time":
                res = DateTimeTool.execute(
                    timezone_name=arguments.get("timezone_name"),
                    offset_days=int(arguments.get("offset_days", 0) or 0),
                )
            elif tool_name == "knowledge_retrieval":
                res = await asyncio.wait_for(
                    KnowledgeRetrievalTool.execute(
                        db=db,
                        user_id=user_id,
                        query=str(arguments.get("query", "")),
                        top_k=int(arguments.get("top_k", 4) or 4),
                        document_ids=attached_document_ids,
                    ),
                    timeout=timeout_s,
                )
            elif tool_name == "document_reader":
                res = await asyncio.wait_for(
                    DocumentReaderTool.execute(
                        db=db,
                        user_id=user_id,
                        document_id=arguments.get("document_id"),
                        filename=arguments.get("filename"),
                        max_chunks=int(arguments.get("max_chunks", 5) or 5),
                    ),
                    timeout=timeout_s,
                )
            elif tool_name == "python_data_analysis":
                res = await asyncio.to_thread(
                    PythonSandboxTool.execute,
                    str(arguments.get("code", "")),
                    min(timeout_s, settings.PYTHON_SANDBOX_TIMEOUT_SECONDS),
                    settings.PYTHON_SANDBOX_MEMORY_MB,
                )
            elif tool_name == "web_search":
                res = await asyncio.wait_for(
                    WebSearchTool.execute(
                        query=str(arguments.get("query", "")),
                        max_results=int(arguments.get("max_results", 4) or 4),
                        enabled=web_policy_enabled,
                    ),
                    timeout=timeout_s,
                )
            elif tool_name == "weather":
                res = await asyncio.wait_for(
                    WeatherTool.execute(
                        location=str(arguments.get("location", "")),
                        target_day=arguments.get("target_day", "current"),
                    ),
                    timeout=timeout_s,
                )
            elif tool_name == "news_search":
                res = await asyncio.wait_for(
                    NewsTool.execute(
                        topic=str(arguments.get("topic", "ai")),
                        max_articles=int(arguments.get("max_articles", 5) or 5),
                    ),
                    timeout=timeout_s,
                )
            elif tool_name == "currency_converter":
                res = await asyncio.wait_for(
                    CurrencyTool.execute(
                        from_currency=str(arguments.get("from_currency", "USD")),
                        to_currency=str(arguments.get("to_currency", "LKR")),
                        amount=float(arguments.get("amount", 1.0) or 1.0),
                    ),
                    timeout=timeout_s,
                )
            else:
                res = {"ok": False, "error": f"No handler for '{tool_name}'"}

            st = "success" if res.get("ok") else str(res.get("status", "error"))
            if st not in ("success", "error", "timeout", "blocked"):
                st = "error"
            return await _log_and_return(res, st, res.get("error"))
        except asyncio.TimeoutError:
            return await _log_and_return(
                {"ok": False, "error": f"Tool '{tool_name}' timed out after {timeout_s}s"},
                "timeout",
                "timeout",
            )
        except Exception as exc:
            return await _log_and_return(
                {"ok": False, "error": f"Tool execution error: {str(exc)[:180]}"},
                "error",
                str(exc)[:180],
            )

    @classmethod
    async def run_proactive_tools(
        cls,
        db: AsyncSession,
        *,
        prompt: str,
        intent: str,
        suggested_tools: List[str],
        ai_config: SystemAIConfig,
        current_user: Optional[User],
        conversation_id: Optional[str],
        web_search_requested: bool,
        attached_document_ids: Optional[List[str]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Deterministically execute high-confidence tools before LLM generation so even compact
        local models produce verified numbers, timestamps, code checks, or web disclosures.
        Returns (tool_records, web_citations).
        """
        records: List[Dict[str, Any]] = []
        web_citations: List[Dict[str, Any]] = []
        call_counts: Dict[str, int] = {}

        if not ai_config.enable_agent_tools and not web_search_requested:
            return records, web_citations

        # 1. Calculator / Unit conversion deterministic trigger
        if "calculator" in suggested_tools or intent == "math":
            expr = CalculatorTool.extract_expression_from_prompt(prompt)
            if expr:
                rec = await cls.execute_tool(
                    db,
                    "calculator",
                    {"expression": expr},
                    ai_config=ai_config,
                    current_user=current_user,
                    conversation_id=conversation_id,
                    call_counts=call_counts,
                )
                records.append(rec)

        # 2. Date / Time and Exact Age deterministic trigger
        if "date_time" in suggested_tools or intent == "age_date_calc":
            dob_match = re.search(
                r"(?i)(?:born\s+(?:on\s+)?|dob\s*[:=]\s*|birth\s*date\s*[:=]\s*)(\d{1,2}\s+[a-zA-Z]+\s+\d{4}|\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4})",
                prompt,
            )
            tz_match = re.search(r"\b([A-Za-z]+/[A-Za-z_]+)\b", prompt)
            args: Dict[str, Any] = {}
            if dob_match:
                args["dob"] = dob_match.group(1).strip()
            if tz_match:
                args["timezone_name"] = tz_match.group(1).strip()

            rec = await cls.execute_tool(
                db,
                "date_time",
                args,
                ai_config=ai_config,
                current_user=current_user,
                conversation_id=conversation_id,
                call_counts=call_counts,
            )
            records.append(rec)

        # 3. Weather live intelligence deterministic trigger
        if "weather" in suggested_tools or intent == "weather":
            target_day = "tomorrow" if "tomorrow" in prompt.lower() else "current"
            loc_match = re.search(
                r"(?i)(?:weather|forecast|rain|temperature|climate)\s+(?:in|for|at|of)?\s*([a-zA-Z\s]+?)(?:\s+(?:tomorrow|today|this week|now|currently)|\?|\.|$)",
                prompt,
            )
            loc = loc_match.group(1).strip() if loc_match else "Colombo"
            if len(loc) > 1 and loc.lower() not in ("what", "is", "the", "like", "how"):
                rec = await cls.execute_tool(
                    db,
                    "weather",
                    {"location": loc, "target_day": target_day},
                    ai_config=ai_config,
                    current_user=current_user,
                    conversation_id=conversation_id,
                    call_counts=call_counts,
                )
                records.append(rec)

        # 4. Currency conversion deterministic trigger
        if "currency_converter" in suggested_tools or intent == "currency":
            curr_match = re.search(
                r"(?i)(?:convert\s+)?(\d+(?:\.\d+)?)\s*([a-zA-Z]{3})\s+(?:to|in|into)\s+([a-zA-Z]{3})",
                prompt,
            )
            if curr_match:
                rec = await cls.execute_tool(
                    db,
                    "currency_converter",
                    {
                        "amount": float(curr_match.group(1)),
                        "from_currency": curr_match.group(2).upper(),
                        "to_currency": curr_match.group(3).upper(),
                    },
                    ai_config=ai_config,
                    current_user=current_user,
                    conversation_id=conversation_id,
                    call_counts=call_counts,
                )
                records.append(rec)

        # 5. News search deterministic trigger
        if "news_search" in suggested_tools or intent == "news":
            topic = "ai"
            for t_candidate in ("ai", "artificial intelligence", "technology", "tech", "science", "business", "education", "sri lanka", "world"):
                if t_candidate in prompt.lower():
                    topic = t_candidate
                    break
            rec = await cls.execute_tool(
                db,
                "news_search",
                {"topic": topic, "max_articles": 4},
                ai_config=ai_config,
                current_user=current_user,
                conversation_id=conversation_id,
                call_counts=call_counts,
            )
            records.append(rec)
            for item in rec.get("articles", []):
                web_citations.append(
                    {
                        "source_type": "news",
                        "title": item.get("title", "News Source"),
                        "url": item.get("url", ""),
                        "snippet": item.get("snippet", "")[:240],
                    }
                )

        # 6. Direct fenced Python analysis execution when user explicitly asks to run/execute/plot python
        if "python_data_analysis" in suggested_tools and any(
            k in prompt.lower() for k in ("run python", "execute", "plot ", "chart", "run this code")
        ):
            m = _PY_BLOCK_RE.search(prompt)
            if m:
                rec = await cls.execute_tool(
                    db,
                    "python_data_analysis",
                    {"code": m.group(1).strip()},
                    ai_config=ai_config,
                    current_user=current_user,
                    conversation_id=conversation_id,
                    call_counts=call_counts,
                )
                records.append(rec)

        # 4. Web search (explicitly toggled or strong web-research intent)
        if web_search_requested or "web_search" in suggested_tools:
            rec = await cls.execute_tool(
                db,
                "web_search",
                {"query": prompt[:280], "max_results": 4},
                ai_config=ai_config,
                current_user=current_user,
                conversation_id=conversation_id,
                call_counts=call_counts,
                web_search_requested=web_search_requested,
            )
            records.append(rec)
            for item in rec.get("results", []):
                web_citations.append(
                    {
                        "source_type": "web",
                        "title": item.get("title", "Web Source"),
                        "url": item.get("url", ""),
                        "snippet": item.get("snippet", "")[:240],
                    }
                )

        return records, web_citations
