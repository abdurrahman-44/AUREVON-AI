import math
import statistics
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import AIRequestLog, Conversation, User
from backend.app.schemas.admin import (
    AIPerformanceMetrics,
    AdminAnalyticsResponse,
    AnalyticsOverviewResponse,
    DailyTimeSeriesPoint,
    ErrorBreakdownItem,
    ModelUtilizationItem,
)


def _to_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _to_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def resolve_date_window(
    range_key: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Tuple[str, datetime, datetime, bool]:
    now_utc = datetime.now(timezone.utc)
    normalized = (range_key or "7d").lower().strip()

    if normalized == "24h":
        return "24h", now_utc - timedelta(hours=24), now_utc, True
    if normalized == "30d":
        return "30d", now_utc - timedelta(days=30), now_utc, False
    if normalized == "90d":
        return "90d", now_utc - timedelta(days=90), now_utc, False
    if normalized == "custom" and start_date and end_date:
        s = _to_aware_utc(start_date)
        e = _to_aware_utc(end_date)
        if e < s:
            s, e = e, s
        hourly = (e - s).total_seconds() <= 48 * 3600
        return "custom", s, e, hourly

    return "7d", now_utc - timedelta(days=7), now_utc, False


def _percentile(sorted_vals: List[int], pct: float) -> Optional[float]:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    return round(sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f), 1)


async def compute_admin_analytics(
    db: AsyncSession,
    range_key: str = "7d",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> AdminAnalyticsResponse:
    label, win_start_aware, win_end_aware, use_hourly = resolve_date_window(range_key, start_date, end_date)
    win_start = _to_naive_utc(win_start_aware)
    win_end = _to_naive_utc(win_end_aware)

    now_naive = _to_naive_utc(datetime.now(timezone.utc))
    cutoff_24h = now_naive - timedelta(hours=24)
    cutoff_7d = now_naive - timedelta(days=7)
    cutoff_30d = now_naive - timedelta(days=30)

    # 1. Database-aggregated user & conversation overview metrics
    total_users = int((await db.execute(select(func.count(User.id)))).scalar_one() or 0)
    active_24h = int(
        (await db.execute(select(func.count(User.id)).where(User.last_active_at >= cutoff_24h))).scalar_one() or 0
    )
    active_7d = int(
        (await db.execute(select(func.count(User.id)).where(User.last_active_at >= cutoff_7d))).scalar_one() or 0
    )
    active_30d = int(
        (await db.execute(select(func.count(User.id)).where(User.last_active_at >= cutoff_30d))).scalar_one() or 0
    )
    total_conversations = int((await db.execute(select(func.count(Conversation.id)))).scalar_one() or 0)
    today_utc_start = now_naive.replace(hour=0, minute=0, second=0, microsecond=0)
    requests_today = int(
        (await db.execute(select(func.count(AIRequestLog.id)).where(AIRequestLog.created_at >= today_utc_start))).scalar_one()
        or 0
    )
    new_users_count = int(
        (
            await db.execute(
                select(func.count(User.id)).where(User.created_at >= win_start, User.created_at <= win_end)
            )
        ).scalar_one()
        or 0
    )

    # 2. Database-aggregated AI request totals inside window
    agg_stmt = select(
        func.count(AIRequestLog.id).label("total_req"),
        func.sum(case((AIRequestLog.success.is_(True), 1), else_=0)).label("ok_req"),
        func.sum(case((AIRequestLog.success.is_(False), 1), else_=0)).label("fail_req"),
        func.avg(AIRequestLog.duration_ms).label("avg_lat"),
        func.avg(AIRequestLog.first_token_ms).label("avg_ttft"),
        func.sum(AIRequestLog.prompt_tokens).label("sum_prompt"),
        func.sum(AIRequestLog.completion_tokens).label("sum_completion"),
        func.sum(AIRequestLog.total_tokens).label("sum_total"),
    ).where(AIRequestLog.created_at >= win_start, AIRequestLog.created_at <= win_end)

    agg_row = (await db.execute(agg_stmt)).one()
    total_req = int(agg_row.total_req or 0)
    ok_req = int(agg_row.ok_req or 0)
    fail_req = int(agg_row.fail_req or 0)
    success_rate = round((ok_req / total_req) * 100.0, 2) if total_req > 0 else None

    overview = AnalyticsOverviewResponse(
        total_users=total_users,
        active_users_24h=active_24h,
        active_users_7d=active_7d,
        active_users_30d=active_30d,
        total_conversations=total_conversations,
        total_ai_requests=total_req,
        requests_today=requests_today,
        new_users=new_users_count,
        successful_requests=ok_req,
        failed_requests=fail_req,
        success_rate_pct=success_rate,
    )

    # 3. Database-aggregated model utilization & error breakdowns
    model_stmt = (
        select(
            AIRequestLog.provider,
            AIRequestLog.model,
            func.count(AIRequestLog.id).label("req_cnt"),
            func.sum(case((AIRequestLog.success.is_(True), 1), else_=0)).label("ok_cnt"),
            func.sum(case((AIRequestLog.success.is_(False), 1), else_=0)).label("fail_cnt"),
            func.sum(AIRequestLog.total_tokens).label("tok_sum"),
            func.avg(AIRequestLog.duration_ms).label("avg_lat"),
        )
        .where(AIRequestLog.created_at >= win_start, AIRequestLog.created_at <= win_end)
        .group_by(AIRequestLog.provider, AIRequestLog.model)
        .order_by(func.count(AIRequestLog.id).desc())
    )
    model_rows = (await db.execute(model_stmt)).all()
    model_utilization = [
        ModelUtilizationItem(
            provider=r.provider,
            model=r.model,
            request_count=int(r.req_cnt or 0),
            successful_count=int(r.ok_cnt or 0),
            failed_count=int(r.fail_cnt or 0),
            total_tokens=int(r.tok_sum) if r.tok_sum is not None else None,
            avg_latency_ms=round(float(r.avg_lat), 1) if r.avg_lat is not None else None,
        )
        for r in model_rows
    ]

    err_stmt = (
        select(
            func.coalesce(AIRequestLog.error_category, "unknown").label("category"),
            func.count(AIRequestLog.id).label("cnt"),
        )
        .where(
            AIRequestLog.created_at >= win_start,
            AIRequestLog.created_at <= win_end,
            AIRequestLog.success.is_(False),
        )
        .group_by("category")
        .order_by(func.count(AIRequestLog.id).desc())
    )
    error_breakdown = [
        ErrorBreakdownItem(error_category=str(r.category), count=int(r.cnt or 0))
        for r in (await db.execute(err_stmt)).all()
    ]

    # 4. Fetch lightweight window points for true Median/P95 and chart buckets
    log_pts_stmt = (
        select(
            AIRequestLog.created_at,
            AIRequestLog.duration_ms,
            AIRequestLog.prompt_tokens,
            AIRequestLog.completion_tokens,
            AIRequestLog.total_tokens,
            AIRequestLog.success,
            AIRequestLog.user_id,
        )
        .where(AIRequestLog.created_at >= win_start, AIRequestLog.created_at <= win_end)
        .order_by(AIRequestLog.created_at.asc())
    )
    log_rows = (await db.execute(log_pts_stmt)).all()

    durations = sorted(int(r.duration_ms) for r in log_rows if r.duration_ms is not None)
    median_lat = round(float(statistics.median(durations)), 1) if durations else None
    p95_lat = _percentile(durations, 95.0)

    elapsed_seconds = max(60.0, (win_end_aware - win_start_aware).total_seconds())
    elapsed_minutes = elapsed_seconds / 60.0
    elapsed_days = max(1.0 / 24.0, elapsed_seconds / 86400.0)

    performance = AIPerformanceMetrics(
        avg_latency_ms=round(float(agg_row.avg_lat), 1) if agg_row.avg_lat is not None else None,
        median_latency_ms=median_lat,
        p95_latency_ms=p95_lat,
        avg_first_token_ms=round(float(agg_row.avg_ttft), 1) if agg_row.avg_ttft is not None else None,
        prompt_tokens=int(agg_row.sum_prompt) if agg_row.sum_prompt is not None else None,
        completion_tokens=int(agg_row.sum_completion) if agg_row.sum_completion is not None else None,
        total_tokens=int(agg_row.sum_total) if agg_row.sum_total is not None else None,
        requests_per_minute=round(total_req / elapsed_minutes, 3),
        requests_per_day=round(total_req / elapsed_days, 2),
    )

    # 5. Time series bucketing (hourly for <= 48h, daily otherwise)
    new_users_rows = (
        await db.execute(
            select(User.created_at).where(User.created_at >= win_start, User.created_at <= win_end)
        )
    ).scalars().all()

    fmt = "%Y-%m-%d %H:00" if use_hourly else "%Y-%m-%d"
    step = timedelta(hours=1) if use_hourly else timedelta(days=1)

    buckets: Dict[str, dict] = {}
    cursor = _to_naive_utc(win_start_aware).replace(minute=0, second=0, microsecond=0)
    if not use_hourly:
        cursor = cursor.replace(hour=0)
    end_cursor = _to_naive_utc(win_end_aware)

    while cursor <= end_cursor:
        key = cursor.strftime(fmt)
        if key not in buckets:
            buckets[key] = {
                "requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "new_users": 0,
                "active_user_ids": set(),
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "latencies": [],
            }
        cursor += step

    for created_at in new_users_rows:
        key = _to_naive_utc(created_at).strftime(fmt)
        if key in buckets:
            buckets[key]["new_users"] += 1

    for r in log_rows:
        key = _to_naive_utc(r.created_at).strftime(fmt)
        if key not in buckets:
            buckets[key] = {
                "requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "new_users": 0,
                "active_user_ids": set(),
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "latencies": [],
            }
        b = buckets[key]
        b["requests"] += 1
        if r.success:
            b["successful_requests"] += 1
        else:
            b["failed_requests"] += 1
        if r.user_id:
            b["active_user_ids"].add(r.user_id)
        if r.prompt_tokens is not None:
            b["prompt_tokens"] += int(r.prompt_tokens)
        if r.completion_tokens is not None:
            b["completion_tokens"] += int(r.completion_tokens)
        if r.total_tokens is not None:
            b["total_tokens"] += int(r.total_tokens)
        if r.duration_ms is not None:
            b["latencies"].append(int(r.duration_ms))

    time_series = [
        DailyTimeSeriesPoint(
            date=k,
            requests=b["requests"],
            successful_requests=b["successful_requests"],
            failed_requests=b["failed_requests"],
            new_users=b["new_users"],
            active_users=len(b["active_user_ids"]),
            prompt_tokens=b["prompt_tokens"],
            completion_tokens=b["completion_tokens"],
            total_tokens=b["total_tokens"],
            avg_latency_ms=round(sum(b["latencies"]) / len(b["latencies"]), 1) if b["latencies"] else None,
        )
        for k, b in sorted(buckets.items(), key=lambda item: item[0])
    ]

    return AdminAnalyticsResponse(
        range_label=label,
        start_date=win_start_aware,
        end_date=win_end_aware,
        overview=overview,
        performance=performance,
        model_utilization=model_utilization,
        error_breakdown=error_breakdown,
        time_series=time_series,
    )
