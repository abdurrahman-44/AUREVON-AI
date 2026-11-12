from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from fastapi import Request
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import (
    AIRequestLog,
    APIRequestLog,
    AdminAuditLog,
    RevokedToken,
    SecurityEvent,
)

_SENSITIVE_FRAGMENTS = ("password", "secret", "token", "api_key", "authorization", "totp")


def extract_client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()[:64]
    if request.client and request.client.host:
        return str(request.client.host)[:64]
    return None


def sanitize_details(details: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not details:
        return None
    cleaned: Dict[str, Any] = {}
    for k, v in details.items():
        lk = str(k).lower()
        if any(frag in lk for frag in _SENSITIVE_FRAGMENTS):
            cleaned[k] = "[REDACTED]"
        elif isinstance(v, dict):
            cleaned[k] = sanitize_details(v)
        elif isinstance(v, str) and len(v) > 250:
            cleaned[k] = v[:247] + "..."
        else:
            cleaned[k] = v
    return cleaned


async def record_admin_audit(
    db: AsyncSession,
    *,
    actor_user_id: Optional[str],
    actor_username: str,
    action: str,
    summary: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    status: str = "success",
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> AdminAuditLog:
    entry = AdminAuditLog(
        actor_user_id=actor_user_id,
        actor_username=(actor_username or "system")[:64],
        action=action[:64],
        target_type=target_type[:64] if target_type else None,
        target_id=target_id[:64] if target_id else None,
        status=status[:32],
        summary=summary[:255],
        details=sanitize_details(details),
        ip_address=ip_address[:64] if ip_address else None,
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    await db.commit()
    return entry


async def record_security_event(
    db: AsyncSession,
    *,
    event_type: str,
    detail: str,
    severity: str = "info",
    user_id: Optional[str] = None,
    identifier: Optional[str] = None,
    ip_address: Optional[str] = None,
    path: Optional[str] = None,
) -> SecurityEvent:
    masked_identifier = identifier[:255] if identifier else None
    entry = SecurityEvent(
        event_type=event_type[:64],
        severity=severity[:16],
        user_id=user_id,
        identifier=masked_identifier,
        ip_address=ip_address[:64] if ip_address else None,
        path=path[:255] if path else None,
        detail=detail[:255],
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    await db.commit()
    return entry


async def purge_expired_logs(db: AsyncSession, retention_days: int) -> Dict[str, int]:
    """Delete operational telemetry older than retention_days and expired revoked tokens."""
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=max(1, retention_days))
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)

    res_api = await db.execute(delete(APIRequestLog).where(APIRequestLog.created_at < cutoff))
    res_ai = await db.execute(delete(AIRequestLog).where(AIRequestLog.created_at < cutoff))
    res_sec = await db.execute(delete(SecurityEvent).where(SecurityEvent.created_at < cutoff))
    res_audit = await db.execute(delete(AdminAuditLog).where(AdminAuditLog.created_at < cutoff))
    res_tok = await db.execute(delete(RevokedToken).where(RevokedToken.expires_at.is_not(None), RevokedToken.expires_at < now_naive))
    await db.commit()

    return {
        "api_request_logs_deleted": int(res_api.rowcount or 0),
        "ai_request_logs_deleted": int(res_ai.rowcount or 0),
        "security_events_deleted": int(res_sec.rowcount or 0),
        "admin_audit_logs_deleted": int(res_audit.rowcount or 0),
        "expired_revoked_tokens_deleted": int(res_tok.rowcount or 0),
    }
