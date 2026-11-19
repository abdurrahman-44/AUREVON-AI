from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import ToolConfig, ToolExecutionLog, User


DEFAULT_TOOL_SPECS: List[Dict[str, Any]] = [
    {
        "tool_name": "calculator",
        "display_name": "Scientific Calculator & Unit Converter",
        "description": "Evaluates mathematical expressions, scientific functions, and physical/data unit conversions safely via AST.",
        "is_enabled": True,
        "permission_level": "standard",
        "timeout_seconds": 5,
        "max_calls_per_request": 3,
        "schema": {
            "type": "object",
            "properties": {"expression": {"type": "string", "minLength": 1, "maxLength": 250}},
            "required": ["expression"],
        },
    },
    {
        "tool_name": "date_time",
        "display_name": "Date, Time & Timezone",
        "description": "Returns verified current local/UTC date, time, day of week, and timezone conversions.",
        "is_enabled": True,
        "permission_level": "standard",
        "timeout_seconds": 5,
        "max_calls_per_request": 2,
        "schema": {
            "type": "object",
            "properties": {
                "timezone_name": {"type": "string"},
                "offset_days": {"type": "integer", "minimum": -3650, "maximum": 3650},
            },
        },
    },
    {
        "tool_name": "knowledge_retrieval",
        "display_name": "Knowledge Base Search (RAG)",
        "description": "Searches user's indexed documents using SQLite FTS5 + semantic vector scoring with strict tenant isolation.",
        "is_enabled": True,
        "permission_level": "standard",
        "timeout_seconds": 8,
        "max_calls_per_request": 3,
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 500},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 8},
            },
            "required": ["query"],
        },
    },
    {
        "tool_name": "document_reader",
        "display_name": "Document Section Reader",
        "description": "Reads sanitized sections from a specific uploaded document owned by the active user.",
        "is_enabled": True,
        "permission_level": "standard",
        "timeout_seconds": 8,
        "max_calls_per_request": 3,
        "schema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string"},
                "filename": {"type": "string"},
                "max_chunks": {"type": "integer", "minimum": 1, "maximum": 10},
            },
        },
    },
    {
        "tool_name": "python_data_analysis",
        "display_name": "Python Sandbox & SVG Charts",
        "description": "Runs AST-validated Python data analysis scripts in an isolated environment without network or secrets.",
        "is_enabled": True,
        "permission_level": "standard",
        "timeout_seconds": 6,
        "max_calls_per_request": 2,
        "schema": {
            "type": "object",
            "properties": {"code": {"type": "string", "minLength": 1, "maxLength": 8000}},
            "required": ["code"],
        },
    },
    {
        "tool_name": "web_search",
        "display_name": "Live Web Research",
        "description": "Queries public web search endpoints when enabled by platform configuration and online.",
        "is_enabled": False,
        "permission_level": "standard",
        "timeout_seconds": 8,
        "max_calls_per_request": 2,
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 300},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 6},
            },
            "required": ["query"],
        },
    },
    {
        "tool_name": "weather",
        "display_name": "Live Weather & Forecasts",
        "description": "Retrieves verified live meteorological data, hourly/daily forecasts, and rain probabilities for any global or Sri Lankan location.",
        "is_enabled": True,
        "permission_level": "standard",
        "timeout_seconds": 8,
        "max_calls_per_request": 2,
        "schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "minLength": 1, "maxLength": 100},
                "target_day": {"type": "string", "enum": ["current", "today", "tomorrow", "7day"]},
            },
            "required": ["location"],
        },
    },
    {
        "tool_name": "news_search",
        "display_name": "Recent News & Headlines",
        "description": "Retrieves verified recent news and reporting across tech, AI, science, business, world, or Sri Lanka.",
        "is_enabled": True,
        "permission_level": "standard",
        "timeout_seconds": 8,
        "max_calls_per_request": 2,
        "schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "minLength": 1, "maxLength": 100},
                "max_articles": {"type": "integer", "minimum": 1, "maximum": 8},
            },
        },
    },
    {
        "tool_name": "currency_converter",
        "display_name": "Currency & Forex Converter",
        "description": "Calculates verified live currency conversions and exchange rates across major international and regional currencies.",
        "is_enabled": True,
        "permission_level": "standard",
        "timeout_seconds": 6,
        "max_calls_per_request": 3,
        "schema": {
            "type": "object",
            "properties": {
                "from_currency": {"type": "string", "minLength": 2, "maxLength": 6},
                "to_currency": {"type": "string", "minLength": 2, "maxLength": 6},
                "amount": {"type": "number", "minimum": 0.0},
            },
            "required": ["from_currency", "to_currency"],
        },
    },
]

_SPEC_BY_NAME: Dict[str, Dict[str, Any]] = {s["tool_name"]: s for s in DEFAULT_TOOL_SPECS}


class ToolRegistry:
    """Centralized registry, permission store, and usage telemetry aggregator for AI tools."""

    @classmethod
    def get_spec(cls, tool_name: str) -> Optional[Dict[str, Any]]:
        return _SPEC_BY_NAME.get(tool_name)

    @classmethod
    async def ensure_seeded(cls, db: AsyncSession) -> List[ToolConfig]:
        existing = (await db.execute(select(ToolConfig))).scalars().all()
        by_name = {t.tool_name: t for t in existing}
        added = False
        now = datetime.now(timezone.utc)
        for spec in DEFAULT_TOOL_SPECS:
            if spec["tool_name"] not in by_name:
                cfg = ToolConfig(
                    tool_name=spec["tool_name"],
                    display_name=spec["display_name"],
                    description=spec["description"],
                    is_enabled=spec["is_enabled"],
                    permission_level=spec["permission_level"],
                    timeout_seconds=spec["timeout_seconds"],
                    max_calls_per_request=spec["max_calls_per_request"],
                    updated_at=now,
                )
                db.add(cfg)
                by_name[spec["tool_name"]] = cfg
                added = True
        if added:
            await db.commit()
        ordered = [by_name[s["tool_name"]] for s in DEFAULT_TOOL_SPECS if s["tool_name"] in by_name]
        return ordered

    @classmethod
    async def list_tools_with_stats(cls, db: AsyncSession) -> List[Dict[str, Any]]:
        configs = await cls.ensure_seeded(db)
        stats_res = await db.execute(
            select(
                ToolExecutionLog.tool_name,
                func.count(ToolExecutionLog.id),
                func.sum(case((ToolExecutionLog.status == "success", 1), else_=0)),
                func.sum(case((ToolExecutionLog.status != "success", 1), else_=0)),
                func.avg(ToolExecutionLog.duration_ms),
            ).group_by(ToolExecutionLog.tool_name)
        )
        stats_map: Dict[str, Dict[str, Any]] = {}
        for name, total, ok_count, err_count, avg_ms in stats_res.all():
            stats_map[name] = {
                "total_calls": int(total or 0),
                "successful_calls": int(ok_count or 0),
                "failed_calls": int(err_count or 0),
                "avg_duration_ms": round(float(avg_ms), 1) if avg_ms is not None else 0.0,
            }

        out: List[Dict[str, Any]] = []
        for cfg in configs:
            spec = _SPEC_BY_NAME.get(cfg.tool_name, {})
            st = stats_map.get(
                cfg.tool_name,
                {"total_calls": 0, "successful_calls": 0, "failed_calls": 0, "avg_duration_ms": 0.0},
            )
            out.append(
                {
                    "tool_name": cfg.tool_name,
                    "display_name": cfg.display_name,
                    "description": cfg.description,
                    "is_enabled": bool(cfg.is_enabled),
                    "permission_level": cfg.permission_level,
                    "timeout_seconds": int(cfg.timeout_seconds),
                    "max_calls_per_request": int(cfg.max_calls_per_request),
                    "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
                    "schema": spec.get("schema", {}),
                    **st,
                }
            )
        return out

    @classmethod
    async def update_tool(
        cls,
        db: AsyncSession,
        tool_name: str,
        *,
        is_enabled: Optional[bool] = None,
        permission_level: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        max_calls_per_request: Optional[int] = None,
        admin_user: Optional[User] = None,
    ) -> Optional[ToolConfig]:
        await cls.ensure_seeded(db)
        cfg = (await db.execute(select(ToolConfig).where(ToolConfig.tool_name == tool_name))).scalar_one_or_none()
        if not cfg:
            return None
        if is_enabled is not None:
            cfg.is_enabled = bool(is_enabled)
        if permission_level is not None and permission_level in ("standard", "owner_only", "disabled"):
            cfg.permission_level = permission_level
        if timeout_seconds is not None:
            cfg.timeout_seconds = max(1, min(30, int(timeout_seconds)))
        if max_calls_per_request is not None:
            cfg.max_calls_per_request = max(1, min(10, int(max_calls_per_request)))
        if admin_user is not None:
            cfg.updated_by_user_id = admin_user.id
        cfg.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(cfg)
        return cfg

    @classmethod
    def describe_tools_for_prompt(cls, enabled_names: List[str]) -> str:
        if not enabled_names:
            return ""
        lines = [
            "Available verified tools (use ONLY if existing context/results don't already answer the question; emit exact JSON inside <tool_call>...</tool_call>):"
        ]
        for name in enabled_names:
            spec = _SPEC_BY_NAME.get(name)
            if not spec:
                continue
            props = list(spec.get("schema", {}).get("properties", {}).keys())
            lines.append(f'- `{name}` ({", ".join(props)}): {spec["description"]}')
        lines.append('Format: <tool_call>{"name": "tool_name", "arguments": {...}}</tool_call>')
        return "\n".join(lines)
