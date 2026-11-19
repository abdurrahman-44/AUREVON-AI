import asyncio
import platform
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.cache import app_cache
from backend.app.core.config import settings
from backend.app.models.entities import (
    AIRequestLog,
    APIRequestLog,
    AdminAuditLog,
    Conversation,
    ConversationSummary,
    Document,
    DocumentChunk,
    Memory,
    Message,
    PlatformConfig,
    RevokedToken,
    SecurityEvent,
    User,
)
from backend.app.schemas.admin import TerminalCommandInfo, TerminalExecuteResponse
from backend.app.services.analytics import compute_admin_analytics
from backend.app.services.audit import record_admin_audit
from backend.app.services.ai.model_manager import ModelManager
from backend.app.services.intelligence import IntelligenceCoreService
from backend.app.services.tools.registry import ToolRegistry
from backend.app.services.live.currency import CurrencyService
from backend.app.services.live.news import NewsService
from backend.app.services.live.weather import WeatherService
from backend.app.services.system_monitor import (
    PROCESS_STARTED_AT,
    collect_system_monitoring,
    get_uptime_seconds,
    run_system_diagnostics,
    test_ai_model_connection,
)

# Forbidden shell/injection metacharacters
_FORBIDDEN_META_RE = re.compile(r"[;&|`$><\n\r\x00\\]")
# Redact potential secret patterns in outputs/errors
_SECRET_PATTERNS = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"\b(sk|gsk|rk|pk)-[A-Za-z0-9_\-]{8,}\b"),
    re.compile(r"(password|secret|api_key|token)\s*[:=]\s*[^\s,;]+", re.IGNORECASE),
]

# Server-side single-use confirmation tokens: token -> (user_id, normalized_command, expires_at_ts)
_CONFIRM_TOKENS: Dict[str, Tuple[str, str, float]] = {}
_CONFIRM_TTL_SECONDS = 120.0
_TERMINAL_TIMEOUT_SECONDS = 15.0


def redact_secrets(text_val: str) -> str:
    cleaned = text_val
    for pattern in _SECRET_PATTERNS:
        if pattern.groups:
            cleaned = pattern.sub(r"\1[REDACTED]", cleaned)
        else:
            cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned


def _prune_confirm_tokens() -> None:
    now_ts = time.time()
    expired = [tok for tok, (_, _, exp) in _CONFIRM_TOKENS.items() if exp <= now_ts]
    for tok in expired:
        _CONFIRM_TOKENS.pop(tok, None)


def _issue_confirm_token(user_id: str, normalized_cmd: str) -> str:
    _prune_confirm_tokens()
    if len(_CONFIRM_TOKENS) > 128:
        _CONFIRM_TOKENS.clear()
    tok = secrets.token_urlsafe(18)
    _CONFIRM_TOKENS[tok] = (user_id, normalized_cmd, time.time() + _CONFIRM_TTL_SECONDS)
    return tok


def _consume_confirm_token(token: Optional[str], user_id: str, normalized_cmd: str) -> bool:
    _prune_confirm_tokens()
    if not token:
        return False
    entry = _CONFIRM_TOKENS.get(token)
    if not entry:
        return False
    owner_id, expected_cmd, exp = entry
    if owner_id != user_id or expected_cmd != normalized_cmd or exp <= time.time():
        return False
    _CONFIRM_TOKENS.pop(token, None)
    return True


def _format_duration(seconds: int) -> str:
    days, rem = divmod(max(0, seconds), 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    parts: List[str] = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if mins or hours or days:
        parts.append(f"{mins}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


class TerminalCommandRegistry:
    """Strict allowlist administrative diagnostic command registry (zero shell execution)."""

    CATALOG: List[TerminalCommandInfo] = [
        TerminalCommandInfo(
            command="help",
            category="General",
            description="List all approved administrative commands and usages.",
            usage="help",
        ),
        TerminalCommandInfo(
            command="clear",
            category="General",
            description="Clear the active terminal console buffer.",
            usage="clear",
        ),
        TerminalCommandInfo(
            command="status",
            category="System",
            description="Show overall backend, database, uptime, and AI status summary.",
            usage="status",
        ),
        TerminalCommandInfo(
            command="system health",
            category="System",
            description="Inspect backend service health, database connectivity, and provider reachability.",
            usage="system health",
        ),
        TerminalCommandInfo(
            command="system resources",
            category="System",
            description="Inspect CPU, RAM, process memory, and host storage telemetry.",
            usage="system resources",
        ),
        TerminalCommandInfo(
            command="system uptime",
            category="System",
            description="Show API process uptime and boot timestamp.",
            usage="system uptime",
        ),
        TerminalCommandInfo(
            command="system diagnostics",
            category="System",
            description="Run live read-only diagnostics across database, config, AI, disk, and cache.",
            usage="system diagnostics",
        ),
        TerminalCommandInfo(
            command="backend version",
            category="Backend",
            description="Display application version, Python runtime, and host platform metadata.",
            usage="backend version",
        ),
        TerminalCommandInfo(
            command="backend routes",
            category="Backend",
            description="List registered FastAPI application routes (read-only inspection).",
            usage="backend routes",
        ),
        TerminalCommandInfo(
            command="db stats",
            category="Database",
            description="Count rows across core, audit, security, and telemetry tables.",
            usage="db stats",
        ),
        TerminalCommandInfo(
            command="db tables",
            category="Database",
            description="Alias for db stats showing table record counts.",
            usage="db tables",
        ),
        TerminalCommandInfo(
            command="ai status",
            category="AI",
            description="Show active AI provider, model, parameters, and configured key flags (redacted).",
            usage="ai status",
        ),
        TerminalCommandInfo(
            command="ai models",
            category="AI",
            description="Check AI providers and list currently discoverable models.",
            usage="ai models",
        ),
        TerminalCommandInfo(
            command="ai test",
            category="AI",
            description="Run a bounded live connectivity probe against the active provider and model.",
            usage="ai test",
        ),
        TerminalCommandInfo(
            command="ai model",
            category="AI",
            description="Show active default model, coding specialist, fallback, and live loaded RAM state.",
            usage="ai model",
        ),
        TerminalCommandInfo(
            command="ai latency",
            category="AI",
            description="Show 24h and 7d AI average latency, TTFT, and success rates.",
            usage="ai latency",
        ),
        TerminalCommandInfo(
            command="ai memory",
            category="AI",
            description="Inspect loaded Ollama RAM/VRAM models, user memories, and rolling summaries.",
            usage="ai memory",
        ),
        TerminalCommandInfo(
            command="ai tools",
            category="AI",
            description="List registered AI tools with status, permission level, and call metrics.",
            usage="ai tools",
        ),
        TerminalCommandInfo(
            command="ai tools list",
            category="AI",
            description="Detailed listing of all registered tools and telemetry counters.",
            usage="ai tools list",
        ),
        TerminalCommandInfo(
            command="ai knowledge status",
            category="AI",
            description="Check uploaded knowledge documents, chunk totals, and SQLite FTS5 index status.",
            usage="ai knowledge status",
        ),
        TerminalCommandInfo(
            command="ai diagnostics",
            category="AI",
            description="Run comprehensive Intelligence Engine readiness and health diagnostics.",
            usage="ai diagnostics",
        ),
        TerminalCommandInfo(
            command="ai weather",
            category="AI",
            description="Test live weather service and forecast retrieval (Open-Meteo).",
            usage="ai weather [location]",
        ),
        TerminalCommandInfo(
            command="ai news",
            category="AI",
            description="Test live news search and headlines retrieval.",
            usage="ai news [topic]",
        ),
        TerminalCommandInfo(
            command="ai currency",
            category="AI",
            description="Test live currency exchange rate service (USD to LKR).",
            usage="ai currency [from] [to]",
        ),
        TerminalCommandInfo(
            command="users count",
            category="Users",
            description="Summarize user accounts by status, role, and 2FA enrollment.",
            usage="users count",
        ),
        TerminalCommandInfo(
            command="analytics summary",
            category="Analytics",
            description="Summarize 24h and 7d AI volume, success rate, tokens, and latency.",
            usage="analytics summary",
        ),
        TerminalCommandInfo(
            command="logs recent",
            category="Logs",
            description="Show recent failed AI requests and sanitized security/app events (max 50).",
            usage="logs recent [count]",
        ),
        TerminalCommandInfo(
            command="audit recent",
            category="Logs",
            description="Show recent administrative audit trail entries (max 50).",
            usage="audit recent [count]",
        ),
        TerminalCommandInfo(
            command="cache status",
            category="Maintenance",
            description="Inspect in-memory Control Centre cache keys and entry count.",
            usage="cache status",
        ),
        TerminalCommandInfo(
            command="cache clear",
            category="Maintenance",
            description="Clear Control Centre TTL cache entries (requires interactive confirmation).",
            usage="cache clear",
            requires_confirmation=True,
        ),
    ]

    @classmethod
    def list_commands(cls) -> List[TerminalCommandInfo]:
        return cls.CATALOG

    @classmethod
    def parse_command(cls, raw_command: str) -> Tuple[Optional[str], List[str], Optional[str]]:
        stripped = (raw_command or "").strip()
        if not stripped:
            return None, [], "Empty command. Type 'help' to list allowed commands."

        if _FORBIDDEN_META_RE.search(stripped):
            return (
                None,
                [],
                "Rejected: shell operators, chaining, redirection, quotes, or control characters are blocked.",
            )

        if any(ch in stripped for ch in ('"', "'", "(", ")", "{", "}")):
            return (
                None,
                [],
                "Rejected: unsupported syntax. Use plain allowlisted command tokens only.",
            )

        tokens = [t.lower() for t in stripped.split() if t]
        if not tokens:
            return None, [], "Empty command. Type 'help' to list allowed commands."

        # Match three-word commands, then two-word commands, then single-word commands
        if len(tokens) >= 3:
            three = f"{tokens[0]} {tokens[1]} {tokens[2]}"
            three_word_commands = {
                "ai tools list",
                "ai knowledge status",
            }
            if three in three_word_commands:
                return three, tokens[3:], None

        if len(tokens) >= 2:
            two = f"{tokens[0]} {tokens[1]}"
            two_word_commands = {
                "system health",
                "system resources",
                "system uptime",
                "system diagnostics",
                "backend version",
                "backend routes",
                "db stats",
                "db tables",
                "ai status",
                "ai models",
                "ai test",
                "ai model",
                "ai latency",
                "ai memory",
                "ai tools",
                "ai diagnostics",
                "ai weather",
                "ai news",
                "ai currency",
                "users count",
                "analytics summary",
                "logs recent",
                "audit recent",
                "cache status",
                "cache clear",
            }
            if two in two_word_commands:
                return two, tokens[2:], None

        single_word_commands = {"help", "clear", "status"}
        if tokens[0] in single_word_commands:
            return tokens[0], tokens[1:], None

        return (
            None,
            [],
            f"Unknown or disallowed command '{redact_secrets(stripped[:80])}'. Type 'help' to view allowed commands.",
        )


def _parse_bounded_limit(args: List[str], default: int = 10, max_limit: int = 50) -> Tuple[Optional[int], Optional[str]]:
    if not args:
        return default, None
    if len(args) > 1:
        return None, "Too many arguments. Expected an optional integer count."
    if not args[0].isdigit():
        return None, f"Invalid count '{args[0]}'. Expected a positive integer (1..{max_limit})."
    val = int(args[0])
    if val < 1 or val > max_limit:
        return None, f"Count must be between 1 and {max_limit}."
    return val, None


async def execute_terminal_command(
    *,
    db: AsyncSession,
    raw_command: str,
    actor_user: User,
    confirm_token: Optional[str] = None,
    ip_address: Optional[str] = None,
    app_routes: Optional[List[Dict[str, Any]]] = None,
) -> TerminalExecuteResponse:
    started = time.perf_counter()
    now_utc = datetime.now(timezone.utc)
    safe_cmd_for_log = redact_secrets((raw_command or "").strip()[:160])

    canonical, args, parse_err = TerminalCommandRegistry.parse_command(raw_command)
    if parse_err or not canonical:
        duration_ms = max(1, int((time.perf_counter() - started) * 1000))
        await record_admin_audit(
            db,
            actor_user_id=actor_user.id,
            actor_username=actor_user.username,
            action="terminal.execute",
            target_type="terminal",
            status="denied",
            summary=f"Rejected command: {safe_cmd_for_log}",
            details={"reason": parse_err or "disallowed"},
            ip_address=ip_address,
        )
        await db.commit()
        return TerminalExecuteResponse(
            command=safe_cmd_for_log,
            status="rejected",
            exit_code=1,
            duration_ms=duration_ms,
            executed_at=now_utc,
            output=parse_err or "Command rejected.",
        )

    # Reject unexpected extra args on zero-arg commands
    if canonical not in {"logs recent", "audit recent", "ai weather", "ai news", "ai currency"} and args:
        msg = f"Command '{canonical}' does not accept arguments (received: {' '.join(args)})."
        duration_ms = max(1, int((time.perf_counter() - started) * 1000))
        await record_admin_audit(
            db,
            actor_user_id=actor_user.id,
            actor_username=actor_user.username,
            action="terminal.execute",
            target_type="terminal",
            status="error",
            summary=f"Invalid arguments for {canonical}",
            ip_address=ip_address,
        )
        await db.commit()
        return TerminalExecuteResponse(
            command=canonical,
            status="error",
            exit_code=1,
            duration_ms=duration_ms,
            executed_at=now_utc,
            output=msg,
        )

    # Interactive confirmation gate for mutating commands
    if canonical == "cache clear" and not _consume_confirm_token(confirm_token, actor_user.id, canonical):
        tok = _issue_confirm_token(actor_user.id, canonical)
        duration_ms = max(1, int((time.perf_counter() - started) * 1000))
        await record_admin_audit(
            db,
            actor_user_id=actor_user.id,
            actor_username=actor_user.username,
            action="terminal.execute",
            target_type="cache",
            status="pending_confirmation",
            summary="Confirmation requested for cache clear",
            ip_address=ip_address,
        )
        await db.commit()
        return TerminalExecuteResponse(
            command=canonical,
            status="confirmation_required",
            exit_code=2,
            duration_ms=duration_ms,
            executed_at=now_utc,
            output=(
                "Confirmation required: 'cache clear' will purge all Control Centre TTL cache entries. "
                "Approve the confirmation prompt to execute."
            ),
            requires_confirmation=True,
            confirm_token=tok,
        )

    async def _dispatch() -> Tuple[str, Any, int, str]:
        if canonical == "help":
            lines = ["AUREVON Control Centre — Approved Operational Commands", ""]
            by_cat: Dict[str, List[TerminalCommandInfo]] = {}
            for item in TerminalCommandRegistry.list_commands():
                by_cat.setdefault(item.category, []).append(item)
            for cat, cmds in by_cat.items():
                lines.append(f"[{cat}]")
                for c in cmds:
                    suffix = " (requires confirm)" if c.requires_confirmation else ""
                    lines.append(f"  {c.usage:<22} {c.description}{suffix}")
                lines.append("")
            return "\n".join(lines).rstrip(), [c.model_dump() for c in TerminalCommandRegistry.list_commands()], 0, "ok"

        if canonical == "clear":
            return "Terminal buffer cleared.", {"action": "clear_terminal"}, 0, "ok"

        if canonical in {"status", "system health"}:
            intel = await IntelligenceCoreService.ensure_initialized(db)
            mon = await collect_system_monitoring(db, intel.active_provider, intel.active_model)
            lines = [
                f"Backend Status     : {mon.backend_status.upper()}",
                f"Database           : {'connected' if mon.database_connected else 'disconnected'} ({mon.database_dialect})",
                f"Process Uptime     : {_format_duration(mon.uptime_seconds or 0)}",
                f"Host Environment   : {mon.host_environment} (PID {mon.process_id})",
                f"Active AI Target   : {mon.active_provider} / {mon.active_model}",
                "Providers          :",
            ]
            for ph in mon.provider_health:
                state = "healthy" if ph.available else f"unavailable ({ph.error or 'unreachable'})"
                lines.append(f"  - {ph.provider:<12} : {state} [{ph.models_count} models]")
            return "\n".join(lines), mon.model_dump(mode="json"), 0, "ok"

        if canonical == "system resources":
            intel = await IntelligenceCoreService.ensure_initialized(db)
            mon = await collect_system_monitoring(db, intel.active_provider, intel.active_model)
            fmt_num = lambda v, suffix="": f"{v}{suffix}" if v is not None else "Unavailable"
            lines = [
                f"Host Scope         : {mon.host_environment} ({mon.os_platform or 'Unavailable'})",
                f"CPU Utilization    : {fmt_num(mon.cpu_percent, '%')}",
                f"Host RAM Used      : {fmt_num(mon.ram_used_mb, ' MB')} / {fmt_num(mon.ram_total_mb, ' MB')} ({fmt_num(mon.ram_percent, '%')})",
                f"Backend Process RSS: {fmt_num(mon.process_rss_mb, ' MB')}",
                f"Host Storage Used  : {fmt_num(mon.storage_used_gb, ' GB')} / {fmt_num(mon.storage_total_gb, ' GB')} ({fmt_num(mon.storage_percent, '%')}, {fmt_num(mon.storage_free_gb, ' GB')} free)",
            ]
            return "\n".join(lines), {
                "cpu_percent": mon.cpu_percent,
                "ram_used_mb": mon.ram_used_mb,
                "ram_total_mb": mon.ram_total_mb,
                "ram_percent": mon.ram_percent,
                "process_rss_mb": mon.process_rss_mb,
                "storage_total_gb": mon.storage_total_gb,
                "storage_used_gb": mon.storage_used_gb,
                "storage_free_gb": mon.storage_free_gb,
                "storage_percent": mon.storage_percent,
            }, 0, "ok"

        if canonical == "system uptime":
            secs = get_uptime_seconds()
            data = {
                "uptime_seconds": secs,
                "formatted": _format_duration(secs),
                "started_at": PROCESS_STARTED_AT.isoformat(),
            }
            return (
                f"Backend Process Uptime: {_format_duration(secs)} (started {PROCESS_STARTED_AT.isoformat()})",
                data,
                0,
                "ok",
            )

        if canonical == "system diagnostics":
            intel = await IntelligenceCoreService.ensure_initialized(db)
            diag = await run_system_diagnostics(db, intel.active_provider, intel.active_model)
            lines = [
                f"Overall Diagnostics: {diag.overall_status.upper()}",
                f"Scope              : {diag.host_scope_note}",
                "",
            ]
            for c in diag.checks:
                lat = f" ({c.latency_ms} ms)" if c.latency_ms is not None else ""
                lines.append(f"  [{c.status.upper():<4}] {c.name:<28}{lat} — {c.detail}")
            return "\n".join(lines), diag.model_dump(mode="json"), 0, "ok"

        if canonical == "backend version":
            info = {
                "app_name": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "debug": bool(settings.DEBUG),
            }
            lines = [
                f"Application : {info['app_name']} v{info['version']}",
                f"Python      : {info['python_version']}",
                f"Platform    : {info['platform']}",
                f"Debug Mode  : {info['debug']}",
            ]
            return "\n".join(lines), info, 0, "ok"

        if canonical == "backend routes":
            routes = app_routes or []
            lines = [f"Registered API Routes ({len(routes)} total):"]
            for r in routes[:80]:
                methods = ",".join(r.get("methods") or [])
                lines.append(f"  {methods:<12} {r.get('path')}")
            if len(routes) > 80:
                lines.append(f"  ... ({len(routes) - 80} more routes truncated)")
            return "\n".join(lines), routes, 0, "ok"

        if canonical in {"db stats", "db tables"}:
            table_models = [
                ("users", User),
                ("conversations", Conversation),
                ("messages", Message),
                ("documents", Document),
                ("document_chunks", DocumentChunk),
                ("memories", Memory),
                ("ai_request_logs", AIRequestLog),
                ("api_request_logs", APIRequestLog),
                ("admin_audit_logs", AdminAuditLog),
                ("security_events", SecurityEvent),
                ("revoked_tokens", RevokedToken),
                ("platform_configs", PlatformConfig),
            ]
            counts: Dict[str, int] = {}
            for label, model in table_models:
                counts[label] = int((await db.execute(select(func.count()).select_from(model))).scalar_one() or 0)
            lines = ["Database Table Row Counts:"]
            for label, cnt in counts.items():
                lines.append(f"  {label:<20} : {cnt}")
            return "\n".join(lines), counts, 0, "ok"

        if canonical == "ai status":
            cfg = await IntelligenceCoreService.get_admin_config(db)
            lines = [
                f"Active Provider   : {cfg.active_provider}",
                f"Active Model      : {cfg.active_model}",
                f"Fallback          : {cfg.fallback_provider or 'none'} / {cfg.fallback_model or 'none'}",
                f"Context Window    : {cfg.context_window}",
                f"Temperature       : {cfg.temperature}",
                f"Memory Injection  : {cfg.enable_memory_injection}",
                f"RAG Injection     : {cfg.enable_rag_injection}",
                f"Agent Tools       : {cfg.enable_agent_tools}",
                f"User Model Switch : {cfg.allow_user_model_switching}",
                "Configured Keys   : "
                + ", ".join(f"{k}={'set' if v else 'unset'}" for k, v in cfg.provider_keys_configured.items()),
            ]
            return "\n".join(lines), cfg.model_dump(mode="json", exclude={"prompt_versions", "active_prompt"}), 0, "ok"

        if canonical == "ai models":
            from backend.app.services.ai.factory import ProviderFactory

            providers = ProviderFactory.list_all_providers()
            healths = await asyncio.gather(*(p.check_health() for p in providers), return_exceptions=True)
            lines = ["AI Provider Model Discovery:"]
            payload: List[Dict[str, Any]] = []
            for p, h in zip(providers, healths):
                if isinstance(h, Exception):
                    lines.append(f"  [{p.name}] ERROR: {redact_secrets(str(h))[:120]}")
                    payload.append({"provider": p.name, "status": "error", "models": []})
                else:
                    names = list(h.available_models or [])
                    lines.append(f"  [{h.provider}] status={h.status} count={len(names)}")
                    for m in names[:20]:
                        lines.append(f"    - {m}")
                    payload.append({"provider": h.provider, "status": h.status, "models": names})
            return "\n".join(lines), payload, 0, "ok"

        if canonical == "ai test":
            intel = await IntelligenceCoreService.ensure_initialized(db)
            res = await test_ai_model_connection(
                provider_name=intel.active_provider,
                model_name=intel.active_model,
            )
            if res.success:
                out = (
                    f"AI Connectivity Test PASSED ({res.provider} / {res.model}) in {res.latency_ms} ms\n"
                    f"Preview: {redact_secrets(res.response_preview or '[empty response]')}"
                )
                return out, res.model_dump(mode="json"), 0, "ok"
            out = (
                f"AI Connectivity Test FAILED ({res.provider} / {res.model}) in {res.latency_ms} ms\n"
                f"Error: {redact_secrets(res.error_message or 'Unknown error')}"
            )
            return out, res.model_dump(mode="json"), 1, "error"

        if canonical == "ai model":
            intel = await IntelligenceCoreService.ensure_initialized(db)
            ollama_state = await ModelManager.fetch_ollama_runtime_state(force_refresh=True)
            loaded = [m["name"] for m in ollama_state.get("loaded_models", [])]
            data = {
                "active_provider": intel.active_provider,
                "active_model": intel.active_model,
                "coding_model": intel.coding_model,
                "fallback_provider": intel.fallback_provider,
                "fallback_model": intel.fallback_model,
                "context_window": intel.context_window,
                "max_output_tokens": intel.max_output_tokens,
                "keep_alive_seconds": intel.keep_alive_seconds,
                "loaded_in_ram": loaded,
            }
            lines = [
                f"Active Model       : {intel.active_provider} / {intel.active_model}",
                f"Coding Specialist  : {intel.coding_model or 'auto/default'}",
                f"Fallback Target    : {(intel.fallback_provider + '/' + intel.fallback_model) if intel.fallback_model else 'none'}",
                f"Context / Output   : {intel.context_window} ctx / {intel.max_output_tokens} max_tokens",
                f"Keep-Alive         : {intel.keep_alive_seconds}s",
                f"Loaded In RAM      : {', '.join(loaded) if loaded else 'none'}",
            ]
            return "\n".join(lines), data, 0, "ok"

        if canonical == "ai latency":
            a24 = await compute_admin_analytics(db, range_key="24h")
            a7d = await compute_admin_analytics(db, range_key="7d")
            data = {
                "24h_avg_ms": a24.performance.avg_latency_ms,
                "24h_p95_ms": a24.performance.p95_latency_ms,
                "24h_ttft_ms": a24.performance.avg_first_token_ms,
                "7d_avg_ms": a7d.performance.avg_latency_ms,
                "7d_p95_ms": a7d.performance.p95_latency_ms,
                "7d_success_rate_pct": a7d.overview.success_rate_pct,
            }
            lines = [
                f"24h Avg / P95 Latency : {a24.performance.avg_latency_ms or 'N/A'} ms / {a24.performance.p95_latency_ms or 'N/A'} ms",
                f"24h Avg TTFT          : {a24.performance.avg_first_token_ms or 'N/A'} ms",
                f"7d Avg / P95 Latency  : {a7d.performance.avg_latency_ms or 'N/A'} ms / {a7d.performance.p95_latency_ms or 'N/A'} ms",
                f"7d Success Rate       : {a7d.overview.success_rate_pct or 'N/A'}%",
            ]
            return "\n".join(lines), data, 0, "ok"

        if canonical == "ai memory":
            ollama_state = await ModelManager.fetch_ollama_runtime_state(force_refresh=True)
            loaded = ollama_state.get("loaded_models", [])
            mem_count = int((await db.execute(select(func.count(Memory.id)))).scalar() or 0)
            sum_count = int((await db.execute(select(func.count(ConversationSummary.id)))).scalar() or 0)
            data = {
                "loaded_models": loaded,
                "user_memories_count": mem_count,
                "conversation_summaries_count": sum_count,
            }
            lines = [
                f"User Long-Term Memories : {mem_count}",
                f"Conversation Summaries  : {sum_count}",
                f"Loaded Models In RAM    : {len(loaded)}",
            ]
            for lm in loaded:
                lines.append(f"  - {lm['name']} ({lm.get('size_mb', 0)} MB total, {lm.get('vram_mb', 0)} MB VRAM)")
            return "\n".join(lines), data, 0, "ok"

        if canonical in {"ai tools", "ai tools list"}:
            tools = await ToolRegistry.list_tools_with_stats(db)
            lines = [f"Registered AI Tools ({len(tools)}):"]
            for t in tools:
                state = "ENABLED" if t["is_enabled"] else "DISABLED"
                lines.append(
                    f"  - {t['tool_name']:22s} [{state}] perm={t['permission_level']:10s} timeout={t['timeout_seconds']}s calls={t['total_calls']}"
                )
            return "\n".join(lines), {"tools": tools}, 0, "ok"

        if canonical == "ai knowledge status":
            doc_cnt = int((await db.execute(select(func.count(Document.id)))).scalar() or 0)
            chunk_cnt = int((await db.execute(select(func.count(DocumentChunk.id)))).scalar() or 0)
            fts_cnt: Optional[int] = None
            try:
                from sqlalchemy import text as _sqlt
                fts_cnt = int((await db.execute(_sqlt("SELECT COUNT(*) FROM document_chunks_fts"))).scalar() or 0)
            except Exception:
                fts_cnt = None
            data = {
                "documents": doc_cnt,
                "chunks": chunk_cnt,
                "fts5_indexed_chunks": fts_cnt,
                "fts5_active": fts_cnt is not None,
            }
            lines = [
                f"Indexed Documents : {doc_cnt}",
                f"Document Chunks   : {chunk_cnt}",
                f"SQLite FTS5 Index : {fts_cnt if fts_cnt is not None else 'Unavailable'}",
            ]
            return "\n".join(lines), data, 0, "ok"

        if canonical == "ai diagnostics":
            intel = await IntelligenceCoreService.ensure_initialized(db)
            ollama_state = await ModelManager.fetch_ollama_runtime_state(force_refresh=True)
            tools = await ToolRegistry.list_tools_with_stats(db)
            enabled_tools = [t["tool_name"] for t in tools if t["is_enabled"]]
            doc_cnt = int((await db.execute(select(func.count(Document.id)))).scalar() or 0)
            data = {
                "ollama_reachable": bool(ollama_state.get("reachable")),
                "installed_models": [m.get("name") or m.get("id") for m in ollama_state.get("installed_models", [])],
                "active_model": f"{intel.active_provider}/{intel.active_model}",
                "enabled_tools": enabled_tools,
                "documents_indexed": doc_cnt,
                "cloud_enabled": bool(intel.cloud_inference_enabled),
                "require_cloud_consent": bool(intel.require_cloud_consent),
            }
            lines = [
                f"Ollama Runtime   : {'ONLINE' if data['ollama_reachable'] else 'OFFLINE'} ({ollama_state.get('base_url')})",
                f"Installed Models : {', '.join(data['installed_models']) or 'none'}",
                f"Default Model    : {data['active_model']}",
                f"Enabled Tools    : {', '.join(enabled_tools) or 'none'}",
                f"Documents        : {doc_cnt}",
                f"Cloud Policy     : enabled={data['cloud_enabled']}, require_consent={data['require_cloud_consent']}",
            ]
            return "\n".join(lines), data, 0, "ok"

        if canonical == "ai weather":
            loc = " ".join(args).strip() if args else "Colombo"
            w_res = await WeatherService.get_weather(loc)
            if not w_res.get("ok"):
                return f"Weather lookup failed: {w_res.get('error')}", w_res, 1, "error"
            curr = w_res.get("current") or {}
            out_lines = [
                f"Live Weather for {w_res.get('location')}:",
                f"Condition   : {curr.get('condition')}",
                f"Temperature : {curr.get('temperature_c')}°C (Feels like {curr.get('feels_like_c')}°C)",
                f"Humidity    : {curr.get('humidity_pct')}%",
                f"Wind Speed  : {curr.get('wind_speed_kmh')} km/h",
                f"Source      : {w_res.get('source')}",
            ]
            if w_res.get("tomorrow"):
                tm = w_res["tomorrow"]
                out_lines.append(f"Tomorrow    : {tm.get('condition')}, High: {tm.get('temp_max_c')}°C, Rain Prob: {tm.get('rain_probability_pct')}%")
            return "\n".join(out_lines), w_res, 0, "ok"

        if canonical == "ai news":
            topic = " ".join(args).strip() if args else "ai"
            n_res = await NewsService.get_news(topic)
            if not n_res.get("ok"):
                return f"News lookup failed: {n_res.get('error')}", n_res, 1, "error"
            articles = n_res.get("articles") or []
            out_lines = [f"Recent News for '{topic}' ({len(articles)} articles found):"]
            for a in articles:
                out_lines.append(f"  • {a.get('title')} [{a.get('source')}]")
                out_lines.append(f"    {a.get('url')}")
            return "\n".join(out_lines), n_res, 0, "ok"

        if canonical == "ai currency":
            base = args[0].upper() if len(args) > 0 else "USD"
            target = args[1].upper() if len(args) > 1 else "LKR"
            c_res = await CurrencyService.get_exchange_rate(base, target, 1.0)
            if not c_res.get("ok"):
                return f"Currency lookup failed: {c_res.get('error')}", c_res, 1, "error"
            out = f"Live Forex: 1 {base} = {c_res.get('rate')} {target} (Source: {c_res.get('source')}, Date: {c_res.get('date')})"
            return out, c_res, 0, "ok"

        if canonical == "users count":
            total = int((await db.execute(select(func.count(User.id)))).scalar_one() or 0)
            active = int((await db.execute(select(func.count(User.id)).where(User.is_active.is_(True)))).scalar_one() or 0)
            owners = int((await db.execute(select(func.count(User.id)).where(User.role == "owner"))).scalar_one() or 0)
            totp = int((await db.execute(select(func.count(User.id)).where(User.totp_enabled.is_(True)))).scalar_one() or 0)
            data = {
                "total_users": total,
                "active_users": active,
                "suspended_users": max(0, total - active),
                "owner_accounts": owners,
                "standard_users": max(0, total - owners),
                "totp_enabled_users": totp,
            }
            lines = [
                f"Total Users     : {data['total_users']}",
                f"Active          : {data['active_users']}",
                f"Suspended       : {data['suspended_users']}",
                f"Owner Accounts  : {data['owner_accounts']}",
                f"Standard Users  : {data['standard_users']}",
                f"2FA Enabled     : {data['totp_enabled_users']}",
            ]
            return "\n".join(lines), data, 0, "ok"

        if canonical == "analytics summary":
            a24 = await compute_admin_analytics(db, range_key="24h")
            a7d = await compute_admin_analytics(db, range_key="7d")
            sr7 = f"{a7d.overview.success_rate_pct}%" if a7d.overview.success_rate_pct is not None else "Unavailable"
            lat7 = f"{a7d.performance.avg_latency_ms} ms" if a7d.performance.avg_latency_ms is not None else "Unavailable"
            tok7 = str(a7d.performance.total_tokens) if a7d.performance.total_tokens is not None else "Unavailable"
            lines = [
                f"Requests Today (UTC) : {a24.overview.requests_today}",
                f"24h Requests         : {a24.overview.total_ai_requests} (ok={a24.overview.successful_requests}, fail={a24.overview.failed_requests})",
                f"7d Requests          : {a7d.overview.total_ai_requests} (success rate={sr7})",
                f"7d Avg Latency       : {lat7}",
                f"7d Total Tokens      : {tok7}",
                f"Active Users (24h/7d): {a24.overview.active_users_24h} / {a7d.overview.active_users_7d}",
            ]
            return "\n".join(lines), {
                "requests_today": a24.overview.requests_today,
                "24h": a24.overview.model_dump(),
                "7d_overview": a7d.overview.model_dump(),
                "7d_performance": a7d.performance.model_dump(),
            }, 0, "ok"

        if canonical == "logs recent":
            limit, err = _parse_bounded_limit(args, default=10, max_limit=50)
            if err or limit is None:
                return err or "Invalid argument", None, 1, "error"
            failed_rows = list(
                (
                    await db.execute(
                        select(AIRequestLog)
                        .where(AIRequestLog.success.is_(False))
                        .order_by(AIRequestLog.created_at.desc())
                        .limit(limit)
                    )
                ).scalars().all()
            )
            sec_rows = list(
                (
                    await db.execute(
                        select(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(limit)
                    )
                ).scalars().all()
            )
            lines = [f"Recent Failed AI Requests ({len(failed_rows)}):"]
            for r in failed_rows:
                lines.append(
                    f"  {r.created_at.isoformat()} [{r.provider}/{r.model}] {redact_secrets(r.error_message or r.error_category or 'failed')[:120]}"
                )
            lines.append("")
            lines.append(f"Recent Security Events ({len(sec_rows)}):")
            for s in sec_rows:
                lines.append(
                    f"  {s.created_at.isoformat()} [{s.severity.upper()}] {s.event_type} — {redact_secrets(s.detail)[:120]}"
                )
            return "\n".join(lines), {
                "failed_ai_requests": len(failed_rows),
                "security_events": len(sec_rows),
            }, 0, "ok"

        if canonical == "audit recent":
            limit, err = _parse_bounded_limit(args, default=10, max_limit=50)
            if err or limit is None:
                return err or "Invalid argument", None, 1, "error"
            rows = list(
                (
                    await db.execute(
                        select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(limit)
                    )
                ).scalars().all()
            )
            lines = [f"Recent Admin Audit Logs ({len(rows)}):"]
            for r in rows:
                lines.append(
                    f"  {r.created_at.isoformat()} [{r.status}] {r.actor_username} :: {r.action} — {redact_secrets(r.summary)[:120]}"
                )
            return "\n".join(lines), [
                {
                    "id": r.id,
                    "actor_username": r.actor_username,
                    "action": r.action,
                    "status": r.status,
                    "summary": r.summary,
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ], 0, "ok"

        if canonical == "cache status":
            st = app_cache.status()
            lines = [
                f"Cache Active Entries : {st['entries']} / {st['max_entries']}",
                f"Active Keys          : {', '.join(st['keys']) if st['keys'] else 'none'}",
            ]
            return "\n".join(lines), st, 0, "ok"

        if canonical == "cache clear":
            removed = app_cache.clear()
            return (
                f"Control Centre cache cleared ({removed} active entry/entries evicted).",
                {"evicted_entries": removed},
                0,
                "ok",
            )

        return "Command not handled.", None, 1, "error"

    try:
        output_text, structured, exit_code, status_str = await asyncio.wait_for(
            _dispatch(), timeout=_TERMINAL_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        output_text = f"Command '{canonical}' timed out after {_TERMINAL_TIMEOUT_SECONDS}s."
        structured = None
        exit_code = 1
        status_str = "timeout"
    except Exception as exc:
        output_text = f"Command '{canonical}' failed: {redact_secrets(str(exc))[:240]}"
        structured = None
        exit_code = 1
        status_str = "error"

    duration_ms = max(1, int((time.perf_counter() - started) * 1000))
    safe_output = redact_secrets(output_text)

    await record_admin_audit(
        db,
        actor_user_id=actor_user.id,
        actor_username=actor_user.username,
        action="terminal.execute",
        target_type="terminal",
        status="success" if exit_code == 0 else status_str,
        summary=f"Executed '{canonical}' (exit={exit_code})",
        details={"command": canonical, "exit_code": exit_code, "duration_ms": duration_ms},
        ip_address=ip_address,
    )
    await db.commit()

    return TerminalExecuteResponse(
        command=canonical,
        status=status_str,
        exit_code=exit_code,
        duration_ms=duration_ms,
        executed_at=now_utc,
        output=safe_output,
        structured_data=structured,
    )
