import math
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import require_admin
from backend.app.core.config import settings
from backend.app.core.logging import error_tracker
from backend.app.core.rate_limit import rate_limit_dependency
from backend.app.core.security import build_otpauth_uri, generate_totp_secret, verify_totp_code
from backend.app.database.session import get_db
from backend.app.models.entities import (
    AIRequestLog,
    APIRequestLog,
    AdminAuditLog,
    Conversation,
    Document,
    Memory,
    Message,
    SecurityEvent,
    User,
)
from backend.app.repositories.user_repo import UserRepository
from backend.app.schemas.admin import (
    AITestRequest,
    AITestResponse,
    APIRequestLogItem,
    AdminAnalyticsResponse,
    AdminAuditLogItem,
    AdminUserDetailResponse,
    AdminUserItem,
    ErrorLogsResponse,
    LogPruneRequest,
    LogPruneResponse,
    PaginatedAPIRequestLogsResponse,
    PaginatedAdminAuditLogsResponse,
    PaginatedSecurityEventsResponse,
    PaginatedUsersResponse,
    PlatformConfigResponse,
    PlatformConfigUpdateRequest,
    RecentErrorItem,
    SecurityEventItem,
    SystemAIConfigResponse,
    SystemAIConfigUpdateRequest,
    SystemDiagnosticsResponse,
    SystemMonitoringResponse,
    SystemPromptCreateRequest,
    TerminalCommandInfo,
    TerminalExecuteRequest,
    TerminalExecuteResponse,
    TwoFactorSetupResponse,
    TwoFactorStatusResponse,
    TwoFactorVerifyRequest,
    UserRoleUpdateRequest,
    UserStatusUpdateRequest,
)
from backend.app.services.admin_terminal import TerminalCommandRegistry, execute_terminal_command
from backend.app.services.analytics import compute_admin_analytics
from backend.app.services.audit import (
    extract_client_ip,
    purge_expired_logs,
    record_admin_audit,
    record_security_event,
)
from backend.app.services.intelligence import IntelligenceCoreService
from backend.app.services.platform_settings import PlatformSettingsService
from backend.app.services.system_monitor import (
    collect_system_monitoring,
    run_system_diagnostics,
    test_ai_model_connection,
)

router = APIRouter(
    prefix="/admin",
    tags=["Owner Administration"],
    dependencies=[Depends(require_admin)],
)

admin_terminal_rate_limit = rate_limit_dependency(
    "admin_terminal",
    lambda: settings.RATE_LIMIT_ADMIN_TERMINAL_PER_MINUTE,
)


@router.get("/users", response_model=PaginatedUsersResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=100),
    role: Optional[str] = Query(None, pattern="^(user|owner)$"),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List platform users with conversation & AI telemetry summaries (Owner only)."""
    filters = []
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        filters.append(or_(func.lower(User.username).like(term), func.lower(User.email).like(term)))
    if role is not None:
        filters.append(User.role == role)
    if is_active is not None:
        filters.append(User.is_active == is_active)

    count_stmt = select(func.count(User.id))
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = int((await db.execute(count_stmt)).scalar_one() or 0)
    total_pages = max(1, math.ceil(total / page_size))

    conv_sub = (
        select(
            Conversation.user_id.label("uid"),
            func.count(Conversation.id).label("conv_count"),
        )
        .where(Conversation.user_id.is_not(None))
        .group_by(Conversation.user_id)
        .subquery()
    )

    ai_sub = (
        select(
            AIRequestLog.user_id.label("uid"),
            func.count(AIRequestLog.id).label("req_count"),
            func.sum(AIRequestLog.total_tokens).label("tok_sum"),
        )
        .where(AIRequestLog.user_id.is_not(None))
        .group_by(AIRequestLog.user_id)
        .subquery()
    )

    stmt = (
        select(
            User,
            func.coalesce(conv_sub.c.conv_count, 0).label("conv_count"),
            func.coalesce(ai_sub.c.req_count, 0).label("req_count"),
            ai_sub.c.tok_sum.label("tok_sum"),
        )
        .outerjoin(conv_sub, User.id == conv_sub.c.uid)
        .outerjoin(ai_sub, User.id == ai_sub.c.uid)
    )
    if filters:
        stmt = stmt.where(*filters)

    offset = (page - 1) * page_size
    stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(page_size)
    rows = (await db.execute(stmt)).all()

    items = [
        AdminUserItem(
            id=u.id,
            username=u.username,
            email=u.email,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
            last_active_at=u.last_active_at,
            conversation_count=int(conv_count or 0),
            ai_request_count=int(req_count or 0),
            total_tokens=int(tok_sum) if tok_sum is not None else None,
        )
        for u, conv_count, req_count, tok_sum in rows
    ]

    return PaginatedUsersResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse)
async def get_user_detail(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Privacy-safe user profile and usage counters (no credentials or private chat contents)."""
    repo = UserRepository(db)
    target = await repo.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    conv_count = int(
        (await db.execute(select(func.count(Conversation.id)).where(Conversation.user_id == target.id))).scalar_one()
        or 0
    )
    msg_count = int(
        (
            await db.execute(
                select(func.count(Message.id))
                .join(Conversation, Message.conversation_id == Conversation.id)
                .where(Conversation.user_id == target.id)
            )
        ).scalar_one()
        or 0
    )
    doc_count = int(
        (await db.execute(select(func.count(Document.id)).where(Document.user_id == target.id))).scalar_one() or 0
    )
    mem_count = int(
        (await db.execute(select(func.count(Memory.id)).where(Memory.user_id == target.id))).scalar_one() or 0
    )

    ai_total = int(
        (await db.execute(select(func.count(AIRequestLog.id)).where(AIRequestLog.user_id == target.id))).scalar_one()
        or 0
    )
    ai_ok = int(
        (
            await db.execute(
                select(func.count(AIRequestLog.id)).where(
                    AIRequestLog.user_id == target.id, AIRequestLog.success.is_(True)
                )
            )
        ).scalar_one()
        or 0
    )
    ai_fail = max(0, ai_total - ai_ok)
    tok_sum = (
        await db.execute(select(func.sum(AIRequestLog.total_tokens)).where(AIRequestLog.user_id == target.id))
    ).scalar_one()

    recent_models_rows = (
        await db.execute(
            select(AIRequestLog.provider, AIRequestLog.model)
            .where(AIRequestLog.user_id == target.id)
            .order_by(AIRequestLog.created_at.desc())
            .limit(10)
        )
    ).all()
    seen_models: List[str] = []
    for prov, mod in recent_models_rows:
        tag = f"{prov}:{mod}"
        if tag not in seen_models:
            seen_models.append(tag)
        if len(seen_models) >= 5:
            break

    return AdminUserDetailResponse(
        id=target.id,
        username=target.username,
        email=target.email,
        role=target.role,
        is_active=target.is_active,
        totp_enabled=bool(getattr(target, "totp_enabled", False)),
        created_at=target.created_at,
        last_active_at=target.last_active_at,
        conversation_count=conv_count,
        message_count=msg_count,
        document_count=doc_count,
        memory_count=mem_count,
        ai_request_count=ai_total,
        successful_ai_requests=ai_ok,
        failed_ai_requests=ai_fail,
        total_tokens=int(tok_sum) if tok_sum is not None else None,
        recent_ai_models=seen_models,
    )


@router.patch("/users/{user_id}/status", response_model=AdminUserItem)
async def update_user_status(
    user_id: str,
    payload: UserStatusUpdateRequest,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Suspend or reactivate a user account (Owner only)."""
    if user_id == admin_user.id and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot suspend your own active owner account.",
        )

    repo = UserRepository(db)
    target = await repo.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    updated = await repo.set_active_status(user_id, payload.is_active)
    await record_admin_audit(
        db,
        actor_user_id=admin_user.id,
        actor_username=admin_user.username,
        action="user.status.update",
        target_type="user",
        target_id=user_id,
        summary=f"{'Reactivated' if payload.is_active else 'Suspended'} account '{updated.username}'",
        details={"is_active": payload.is_active, "target_username": updated.username},
        ip_address=extract_client_ip(request),
    )
    return await _build_admin_user_item(db, updated)


@router.patch("/users/{user_id}/role", response_model=AdminUserItem)
async def update_user_role(
    user_id: str,
    payload: UserRoleUpdateRequest,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a user's role while preventing removal of the final owner (Owner only)."""
    repo = UserRepository(db)
    target = await repo.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    if target.role == "owner" and payload.role != "owner":
        owner_count = int(
            (await db.execute(select(func.count(User.id)).where(User.role == "owner"))).scalar_one() or 0
        )
        if owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the final owner account.",
            )

    prev_role = target.role
    updated = await repo.set_role(user_id, payload.role)
    await record_admin_audit(
        db,
        actor_user_id=admin_user.id,
        actor_username=admin_user.username,
        action="user.role.update",
        target_type="user",
        target_id=user_id,
        summary=f"Changed role of '{updated.username}' from '{prev_role}' to '{payload.role}'",
        details={"previous_role": prev_role, "new_role": payload.role, "target_username": updated.username},
        ip_address=extract_client_ip(request),
    )
    return await _build_admin_user_item(db, updated)


async def _build_admin_user_item(db: AsyncSession, user: User) -> AdminUserItem:
    conv_count = int(
        (await db.execute(select(func.count(Conversation.id)).where(Conversation.user_id == user.id))).scalar_one() or 0
    )
    ai_row = (
        await db.execute(
            select(func.count(AIRequestLog.id), func.sum(AIRequestLog.total_tokens)).where(AIRequestLog.user_id == user.id)
        )
    ).one()
    return AdminUserItem(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_active_at=user.last_active_at,
        conversation_count=conv_count,
        ai_request_count=int(ai_row[0] or 0),
        total_tokens=int(ai_row[1]) if ai_row[1] is not None else None,
    )


@router.get("/analytics", response_model=AdminAnalyticsResponse)
async def get_admin_analytics(
    range: str = Query("7d", pattern="^(24h|7d|30d|90d|custom)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Return real database-aggregated telemetry, latency percentiles, tokens, and time-series data."""
    return await compute_admin_analytics(db, range_key=range, start_date=start_date, end_date=end_date)


@router.get("/monitoring", response_model=SystemMonitoringResponse)
async def get_admin_monitoring(db: AsyncSession = Depends(get_db)):
    """Return live backend, DB, AI provider, OS CPU/RAM/disk, uptime, cache, and recent error telemetry."""
    config = await IntelligenceCoreService.ensure_initialized(db)
    return await collect_system_monitoring(
        db,
        active_provider=config.active_provider,
        active_model=config.active_model,
    )


@router.get("/diagnostics", response_model=SystemDiagnosticsResponse)
async def get_admin_diagnostics(db: AsyncSession = Depends(get_db)):
    """Run live read-only infrastructure checks (DB, AI provider, config policies, host storage, cache)."""
    config = await IntelligenceCoreService.ensure_initialized(db)
    return await run_system_diagnostics(
        db,
        active_provider=config.active_provider,
        active_model=config.active_model,
    )


@router.get("/intelligence", response_model=SystemAIConfigResponse)
async def get_admin_intelligence_config(db: AsyncSession = Depends(get_db)):
    """Inspect centralized AI model configuration and prompt version history."""
    return await IntelligenceCoreService.get_admin_config(db)


@router.patch("/intelligence", response_model=SystemAIConfigResponse)
async def update_admin_intelligence_config(
    payload: SystemAIConfigUpdateRequest,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update centralized AI provider, model pinning, context window, temperature, or feature toggles."""
    updated = await IntelligenceCoreService.update_config(db, payload, admin_user)
    changed_fields = payload.model_dump(exclude_unset=True)
    await record_admin_audit(
        db,
        actor_user_id=admin_user.id,
        actor_username=admin_user.username,
        action="ai.config.update",
        target_type="intelligence_core",
        summary=f"Updated AI configuration ({', '.join(changed_fields.keys()) or 'no fields'})",
        details=changed_fields,
        ip_address=extract_client_ip(request),
    )
    return updated


@router.post("/intelligence/prompts", response_model=SystemAIConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_system_prompt_version(
    payload: SystemPromptCreateRequest,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a version-controlled master system prompt (optionally activating immediately)."""
    res = await IntelligenceCoreService.create_prompt_version(db, payload, admin_user)
    await record_admin_audit(
        db,
        actor_user_id=admin_user.id,
        actor_username=admin_user.username,
        action="ai.prompt.create",
        target_type="system_prompt",
        summary=f"Created system prompt version '{payload.name}' (activate={payload.activate})",
        details={"name": payload.name, "activate": payload.activate},
        ip_address=extract_client_ip(request),
    )
    return res


@router.post("/ai/test", response_model=AITestResponse)
async def run_ai_connectivity_test(
    payload: AITestRequest,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Execute a live bounded connectivity probe against a specified or currently active AI provider & model."""
    config = await IntelligenceCoreService.ensure_initialized(db)
    target_provider = (payload.provider or config.active_provider).strip().lower()
    target_model = (payload.model or config.active_model).strip()
    result = await test_ai_model_connection(
        provider_name=target_provider,
        model_name=target_model,
        prompt=payload.prompt,
    )
    await record_admin_audit(
        db,
        actor_user_id=admin_user.id,
        actor_username=admin_user.username,
        action="ai.connectivity.test",
        target_type="ai_provider",
        target_id=f"{result.provider}:{result.model}",
        status="success" if result.success else "error",
        summary=f"Tested {result.provider}/{result.model} ({'PASS' if result.success else 'FAIL'}, {result.latency_ms} ms)",
        details={"provider": result.provider, "model": result.model, "latency_ms": result.latency_ms},
        ip_address=extract_client_ip(request),
    )
    return result


@router.get("/terminal/commands", response_model=List[TerminalCommandInfo])
async def list_terminal_commands():
    """Return all allowlisted operational commands supported by the Admin Terminal."""
    return TerminalCommandRegistry.list_commands()


@router.post(
    "/terminal/execute",
    response_model=TerminalExecuteResponse,
    dependencies=[Depends(admin_terminal_rate_limit)],
)
async def execute_admin_terminal_command(
    payload: TerminalExecuteRequest,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Execute an allowlisted read-only diagnostic or confirmed maintenance command (zero OS shell)."""
    route_summaries = []
    for r in getattr(request.app, "routes", []):
        methods = sorted(m for m in (getattr(r, "methods", None) or []) if m not in {"HEAD", "OPTIONS"})
        path = getattr(r, "path", None)
        if path and methods:
            route_summaries.append({"methods": methods, "path": path})
    route_summaries.sort(key=lambda item: item["path"])

    return await execute_terminal_command(
        db=db,
        raw_command=payload.command,
        actor_user=admin_user,
        confirm_token=payload.confirm_token,
        ip_address=extract_client_ip(request),
        app_routes=route_summaries,
    )


@router.get("/logs/requests", response_model=PaginatedAPIRequestLogsResponse)
async def get_api_request_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    method: Optional[str] = Query(None, max_length=16),
    status_code: Optional[int] = Query(None, ge=100, le=599),
    path_search: Optional[str] = Query(None, max_length=120),
    db: AsyncSession = Depends(get_db),
):
    """Return sanitized HTTP API request telemetry logs."""
    filters = []
    if method and method.strip():
        filters.append(APIRequestLog.method == method.strip().upper())
    if status_code is not None:
        filters.append(APIRequestLog.status_code == status_code)
    if path_search and path_search.strip():
        filters.append(func.lower(APIRequestLog.path).like(f"%{path_search.strip().lower()}%"))

    count_stmt = select(func.count(APIRequestLog.id))
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = int((await db.execute(count_stmt)).scalar_one() or 0)
    total_pages = max(1, math.ceil(total / page_size))

    stmt = select(APIRequestLog)
    if filters:
        stmt = stmt.where(*filters)
    stmt = stmt.order_by(APIRequestLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = list((await db.execute(stmt)).scalars().all())

    return PaginatedAPIRequestLogsResponse(
        items=[
            APIRequestLogItem(
                id=r.id,
                method=r.method,
                path=r.path,
                status_code=r.status_code,
                duration_ms=r.duration_ms,
                user_id=r.user_id,
                client_ip=r.client_ip,
                created_at=r.created_at,
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/logs/audit", response_model=PaginatedAdminAuditLogsResponse)
async def get_admin_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    action: Optional[str] = Query(None, max_length=64),
    status_filter: Optional[str] = Query(None, max_length=32),
    search: Optional[str] = Query(None, max_length=120),
    db: AsyncSession = Depends(get_db),
):
    """Return immutable owner & terminal audit trail records."""
    filters = []
    if action and action.strip():
        filters.append(AdminAuditLog.action == action.strip())
    if status_filter and status_filter.strip():
        filters.append(AdminAuditLog.status == status_filter.strip())
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        filters.append(
            or_(
                func.lower(AdminAuditLog.actor_username).like(term),
                func.lower(AdminAuditLog.action).like(term),
                func.lower(AdminAuditLog.summary).like(term),
            )
        )

    count_stmt = select(func.count(AdminAuditLog.id))
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = int((await db.execute(count_stmt)).scalar_one() or 0)
    total_pages = max(1, math.ceil(total / page_size))

    stmt = select(AdminAuditLog)
    if filters:
        stmt = stmt.where(*filters)
    stmt = stmt.order_by(AdminAuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = list((await db.execute(stmt)).scalars().all())

    return PaginatedAdminAuditLogsResponse(
        items=[
            AdminAuditLogItem(
                id=r.id,
                actor_user_id=r.actor_user_id,
                actor_username=r.actor_username,
                action=r.action,
                target_type=r.target_type,
                target_id=r.target_id,
                status=r.status,
                summary=r.summary,
                details=r.details,
                ip_address=r.ip_address,
                created_at=r.created_at,
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/logs/errors", response_model=ErrorLogsResponse)
async def get_recent_error_logs(db: AsyncSession = Depends(get_db)):
    """Return recent failed AI requests and in-process backend application errors."""
    failed_rows = list(
        (
            await db.execute(
                select(AIRequestLog)
                .where(AIRequestLog.success.is_(False))
                .order_by(AIRequestLog.created_at.desc())
                .limit(30)
            )
        ).scalars().all()
    )
    failed_items = [
        RecentErrorItem(
            timestamp=row.created_at,
            source="ai_request",
            category=row.error_category or "ai_error",
            message=row.error_message or "AI request failed",
            model=row.model,
            provider=row.provider,
        )
        for row in failed_rows
    ]
    app_errors = [
        RecentErrorItem(
            timestamp=entry["timestamp"],
            source=entry["source"],
            category=entry["category"],
            message=entry["message"],
        )
        for entry in error_tracker.get_recent(limit=30)
    ]
    return ErrorLogsResponse(failed_ai_requests=failed_items, recent_app_errors=app_errors)


@router.post("/logs/prune", response_model=LogPruneResponse)
async def prune_operational_logs(
    payload: LogPruneRequest,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Purge telemetry and expired revocation records older than retention_days."""
    deleted = await purge_expired_logs(db, payload.retention_days)
    await record_admin_audit(
        db,
        actor_user_id=admin_user.id,
        actor_username=admin_user.username,
        action="logs.prune",
        target_type="telemetry",
        summary=f"Pruned telemetry logs older than {payload.retention_days} day(s)",
        details={"retention_days": payload.retention_days, "deleted": deleted},
        ip_address=extract_client_ip(request),
    )
    return LogPruneResponse(
        retention_days=payload.retention_days,
        deleted=deleted,
        pruned_at=datetime.now(timezone.utc),
    )


@router.get("/security/events", response_model=PaginatedSecurityEventsResponse)
async def get_security_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    event_type: Optional[str] = Query(None, max_length=64),
    severity: Optional[str] = Query(None, pattern="^(info|warning|critical)$"),
    db: AsyncSession = Depends(get_db),
):
    """Inspect recent authentication, admin authorization, and security telemetry events."""
    filters = []
    if event_type and event_type.strip():
        filters.append(SecurityEvent.event_type == event_type.strip())
    if severity:
        filters.append(SecurityEvent.severity == severity)

    count_stmt = select(func.count(SecurityEvent.id))
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = int((await db.execute(count_stmt)).scalar_one() or 0)
    total_pages = max(1, math.ceil(total / page_size))

    stmt = select(SecurityEvent)
    if filters:
        stmt = stmt.where(*filters)
    stmt = stmt.order_by(SecurityEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = list((await db.execute(stmt)).scalars().all())

    return PaginatedSecurityEventsResponse(
        items=[
            SecurityEventItem(
                id=r.id,
                event_type=r.event_type,
                severity=r.severity,
                user_id=r.user_id,
                identifier=r.identifier,
                ip_address=r.ip_address,
                path=r.path,
                detail=r.detail,
                created_at=r.created_at,
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/security/2fa/status", response_model=TwoFactorStatusResponse)
async def get_owner_two_factor_status(admin_user: User = Depends(require_admin)):
    return TwoFactorStatusResponse(totp_enabled=bool(getattr(admin_user, "totp_enabled", False)))


@router.post("/security/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_owner_two_factor(
    request: Request,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Generate a pending RFC 6238 TOTP secret for the owner account (activates after code verification)."""
    secret = generate_totp_secret()
    admin_user.totp_secret = secret
    admin_user.totp_enabled = False
    await db.commit()

    uri = build_otpauth_uri(secret, admin_user.email or admin_user.username, issuer=settings.APP_NAME)
    await record_admin_audit(
        db,
        actor_user_id=admin_user.id,
        actor_username=admin_user.username,
        action="security.2fa.setup",
        target_type="user",
        target_id=admin_user.id,
        summary="Generated new TOTP setup secret (pending verification)",
        ip_address=extract_client_ip(request),
    )
    return TwoFactorSetupResponse(
        secret=secret,
        otpauth_uri=uri,
        issuer=settings.APP_NAME,
        account_name=admin_user.email or admin_user.username,
    )


@router.post("/security/2fa/enable", response_model=TwoFactorStatusResponse)
async def enable_owner_two_factor(
    payload: TwoFactorVerifyRequest,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Verify a 6-digit TOTP code and activate 2FA on the owner account."""
    if not admin_user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA setup has not been initiated yet.")
    if not verify_totp_code(admin_user.totp_secret, payload.code):
        raise HTTPException(status_code=400, detail="Invalid or expired 6-digit verification code.")

    admin_user.totp_enabled = True
    await db.commit()

    ip = extract_client_ip(request)
    await record_security_event(
        db,
        event_type="admin_2fa_enabled",
        severity="info",
        user_id=admin_user.id,
        identifier=admin_user.username,
        ip_address=ip,
        path=request.url.path,
        detail="Owner enabled TOTP two-factor authentication.",
    )
    await record_admin_audit(
        db,
        actor_user_id=admin_user.id,
        actor_username=admin_user.username,
        action="security.2fa.enable",
        target_type="user",
        target_id=admin_user.id,
        summary="Enabled TOTP two-factor authentication",
        ip_address=ip,
    )
    return TwoFactorStatusResponse(totp_enabled=True)


@router.post("/security/2fa/disable", response_model=TwoFactorStatusResponse)
async def disable_owner_two_factor(
    payload: TwoFactorVerifyRequest,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Disable owner 2FA after confirming the current valid 6-digit TOTP code."""
    if not admin_user.totp_enabled or not admin_user.totp_secret:
        raise HTTPException(status_code=400, detail="Two-factor authentication is not currently enabled.")
    if not verify_totp_code(admin_user.totp_secret, payload.code):
        raise HTTPException(status_code=400, detail="Invalid 6-digit verification code.")

    admin_user.totp_enabled = False
    admin_user.totp_secret = None
    await db.commit()

    ip = extract_client_ip(request)
    await record_security_event(
        db,
        event_type="admin_2fa_disabled",
        severity="warning",
        user_id=admin_user.id,
        identifier=admin_user.username,
        ip_address=ip,
        path=request.url.path,
        detail="Owner disabled TOTP two-factor authentication.",
    )
    await record_admin_audit(
        db,
        actor_user_id=admin_user.id,
        actor_username=admin_user.username,
        action="security.2fa.disable",
        target_type="user",
        target_id=admin_user.id,
        summary="Disabled TOTP two-factor authentication",
        ip_address=ip,
    )
    return TwoFactorStatusResponse(totp_enabled=False)


@router.get("/settings", response_model=PlatformConfigResponse)
async def get_platform_settings(db: AsyncSession = Depends(get_db)):
    """Read current runtime platform policies, rate limits, and maintenance configuration."""
    cfg = await PlatformSettingsService.ensure_initialized(db)
    return PlatformConfigResponse(
        app_display_name=cfg.app_display_name,
        maintenance_mode=cfg.maintenance_mode,
        maintenance_message=cfg.maintenance_message,
        allow_public_registration=cfg.allow_public_registration,
        log_retention_days=cfg.log_retention_days,
        auth_rate_limit_per_min=cfg.auth_rate_limit_per_min,
        chat_rate_limit_per_min=cfg.chat_rate_limit_per_min,
        upload_rate_limit_per_min=cfg.upload_rate_limit_per_min,
        enable_api_request_logging=cfg.enable_api_request_logging,
        updated_at=cfg.updated_at,
    )


@router.patch("/settings", response_model=PlatformConfigResponse)
async def update_platform_settings(
    payload: PlatformConfigUpdateRequest,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update runtime platform policies, maintenance mode, public registration, or rate limits."""
    changed = payload.model_dump(exclude_unset=True)
    cfg = await PlatformSettingsService.update_settings(
        db,
        actor_user_id=admin_user.id,
        **changed,
    )
    await record_admin_audit(
        db,
        actor_user_id=admin_user.id,
        actor_username=admin_user.username,
        action="platform.settings.update",
        target_type="platform_config",
        summary=f"Updated platform settings ({', '.join(changed.keys()) or 'no changes'})",
        details=changed,
        ip_address=extract_client_ip(request),
    )
    return PlatformConfigResponse(
        app_display_name=cfg.app_display_name,
        maintenance_mode=cfg.maintenance_mode,
        maintenance_message=cfg.maintenance_message,
        allow_public_registration=cfg.allow_public_registration,
        log_retention_days=cfg.log_retention_days,
        auth_rate_limit_per_min=cfg.auth_rate_limit_per_min,
        chat_rate_limit_per_min=cfg.chat_rate_limit_per_min,
        upload_rate_limit_per_min=cfg.upload_rate_limit_per_min,
        enable_api_request_logging=cfg.enable_api_request_logging,
        updated_at=cfg.updated_at,
    )
