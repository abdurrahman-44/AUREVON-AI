import asyncio
import ctypes
import os
import platform
import shutil
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.cache import app_cache
from backend.app.core.logging import error_tracker
from backend.app.models.entities import (
    AIRequestLog,
    PlatformConfig,
    SystemAIConfig,
)
from backend.app.schemas.admin import (
    AITestResponse,
    DiagnosticCheckItem,
    ProviderConnectivityItem,
    RecentErrorItem,
    SystemDiagnosticsResponse,
    SystemMonitoringResponse,
)
from backend.app.services.ai.factory import ProviderFactory

PROCESS_STARTED_AT = datetime.now(timezone.utc)


def get_uptime_seconds() -> int:
    return max(0, int((datetime.now(timezone.utc) - PROCESS_STARTED_AT).total_seconds()))


def _read_disk_usage() -> Dict[str, Optional[float]]:
    try:
        usage = shutil.disk_usage(os.getcwd())
        total_gb = round(usage.total / (1024 ** 3), 2)
        used_gb = round(usage.used / (1024 ** 3), 2)
        free_gb = round(usage.free / (1024 ** 3), 2)
        pct = round((usage.used / usage.total) * 100.0, 1) if usage.total > 0 else None
        return {
            "storage_total_gb": total_gb,
            "storage_used_gb": used_gb,
            "storage_free_gb": free_gb,
            "storage_percent": pct,
        }
    except Exception:
        return {
            "storage_total_gb": None,
            "storage_used_gb": None,
            "storage_free_gb": None,
            "storage_percent": None,
        }


def _read_windows_memory() -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        mem_status = MEMORYSTATUSEX()
        mem_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem_status)):
            return None, None, None, None

        total_mb = round(mem_status.ullTotalPhys / (1024 * 1024), 1)
        avail_mb = round(mem_status.ullAvailPhys / (1024 * 1024), 1)
        used_mb = round(total_mb - avail_mb, 1)
        pct = round((used_mb / total_mb) * 100.0, 1) if total_mb > 0 else None

        rss_mb: Optional[float] = None
        try:
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            pmc = PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
                rss_mb = round(pmc.WorkingSetSize / (1024 * 1024), 1)
        except Exception:
            rss_mb = None

        return total_mb, used_mb, pct, rss_mb
    except Exception:
        return None, None, None, None


def _read_windows_system_times() -> Optional[Tuple[int, int, int]]:
    try:
        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]

        def to_int(ft: FILETIME) -> int:
            return (ft.dwHighDateTime << 32) | ft.dwLowDateTime

        idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
        if ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            return to_int(idle), to_int(kernel), to_int(user)
    except Exception:
        return None
    return None


def _read_linux_meminfo() -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    try:
        info: Dict[str, int] = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    val = parts[1].strip().split()[0]
                    info[parts[0].strip()] = int(val)
        total_kb = info.get("MemTotal")
        avail_kb = info.get("MemAvailable", info.get("MemFree"))
        if total_kb and avail_kb is not None:
            total_mb = round(total_kb / 1024.0, 1)
            used_mb = round((total_kb - avail_kb) / 1024.0, 1)
            pct = round((used_mb / total_mb) * 100.0, 1)
        else:
            total_mb = used_mb = pct = None

        rss_mb: Optional[float] = None
        with open("/proc/self/status", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    rss_kb = int(line.split(":")[1].strip().split()[0])
                    rss_mb = round(rss_kb / 1024.0, 1)
                    break
        return total_mb, used_mb, pct, rss_mb
    except Exception:
        return None, None, None, None


def _read_linux_cpu_times() -> Optional[Tuple[int, int]]:
    try:
        with open("/proc/stat", "r", encoding="utf-8") as f:
            first = f.readline()
        if not first.startswith("cpu "):
            return None
        nums = [int(x) for x in first.split()[1:]]
        idle = nums[3] + (nums[4] if len(nums) > 4 else 0)
        total = sum(nums)
        return idle, total
    except Exception:
        return None


async def get_host_resource_usage() -> Dict[str, Optional[float]]:
    """Gather genuine host CPU and RAM telemetry without fabricating fallback zeros."""
    try:
        import psutil  # type: ignore

        cpu_pct = round(float(psutil.cpu_percent(interval=0.1)), 1)
        vm = psutil.virtual_memory()
        proc = psutil.Process()
        return {
            "cpu_percent": cpu_pct,
            "ram_total_mb": round(vm.total / (1024 * 1024), 1),
            "ram_used_mb": round(vm.used / (1024 * 1024), 1),
            "ram_percent": round(float(vm.percent), 1),
            "process_rss_mb": round(proc.memory_info().rss / (1024 * 1024), 1),
        }
    except ImportError:
        pass
    except Exception:
        pass

    if sys.platform == "win32":
        total_mb, used_mb, ram_pct, rss_mb = _read_windows_memory()
        cpu_pct: Optional[float] = None
        t1 = _read_windows_system_times()
        if t1 is not None:
            await asyncio.sleep(0.15)
            t2 = _read_windows_system_times()
            if t2 is not None:
                idle_d = t2[0] - t1[0]
                kernel_d = t2[1] - t1[1]
                user_d = t2[2] - t1[2]
                total_sys = kernel_d + user_d
                if total_sys > 0:
                    cpu_pct = round(max(0.0, min(100.0, ((total_sys - idle_d) / total_sys) * 100.0)), 1)
        return {
            "cpu_percent": cpu_pct,
            "ram_total_mb": total_mb,
            "ram_used_mb": used_mb,
            "ram_percent": ram_pct,
            "process_rss_mb": rss_mb,
        }

    total_mb, used_mb, ram_pct, rss_mb = _read_linux_meminfo()
    cpu_pct = None
    l1 = _read_linux_cpu_times()
    if l1 is not None:
        await asyncio.sleep(0.15)
        l2 = _read_linux_cpu_times()
        if l2 is not None:
            idle_d = l2[0] - l1[0]
            total_d = l2[1] - l1[1]
            if total_d > 0:
                cpu_pct = round(max(0.0, min(100.0, ((total_d - idle_d) / total_d) * 100.0)), 1)

    return {
        "cpu_percent": cpu_pct,
        "ram_total_mb": total_mb,
        "ram_used_mb": used_mb,
        "ram_percent": ram_pct,
        "process_rss_mb": rss_mb,
    }


async def collect_system_monitoring(
    db: AsyncSession,
    active_provider: str,
    active_model: str,
) -> SystemMonitoringResponse:
    db_connected = True
    dialect = "unknown"
    try:
        await db.execute(text("SELECT 1"))
        if db.bind is not None:
            dialect = db.bind.dialect.name
    except Exception:
        db_connected = False

    providers = ProviderFactory.list_all_providers()
    health_results = await asyncio.gather(*(p.check_health() for p in providers), return_exceptions=True)
    provider_items = []
    for p, res in zip(providers, health_results):
        if isinstance(res, Exception):
            provider_items.append(
                ProviderConnectivityItem(
                    provider=p.name,
                    available=False,
                    models_count=0,
                    error=str(res)[:160],
                )
            )
        else:
            provider_items.append(
                ProviderConnectivityItem(
                    provider=res.provider,
                    available=(res.status == "healthy"),
                    models_count=len(res.available_models or []),
                    error=res.error_message,
                )
            )

    failed_stmt = (
        select(AIRequestLog)
        .where(AIRequestLog.success.is_(False))
        .order_by(AIRequestLog.created_at.desc())
        .limit(15)
    )
    failed_rows = list((await db.execute(failed_stmt)).scalars().all())
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
        for entry in error_tracker.get_recent(limit=15)
    ]

    resources = await get_host_resource_usage()
    disk = _read_disk_usage()
    host_env = "docker_container" if os.path.exists("/.dockerenv") else "backend_host"

    return SystemMonitoringResponse(
        checked_at=datetime.now(timezone.utc),
        backend_status="healthy" if db_connected else "degraded",
        database_connected=db_connected,
        database_dialect=dialect,
        active_provider=active_provider,
        active_model=active_model,
        provider_health=provider_items,
        cpu_percent=resources["cpu_percent"],
        ram_total_mb=resources["ram_total_mb"],
        ram_used_mb=resources["ram_used_mb"],
        ram_percent=resources["ram_percent"],
        process_rss_mb=resources["process_rss_mb"],
        uptime_seconds=get_uptime_seconds(),
        host_environment=host_env,
        os_platform=platform.platform()[:96],
        python_version=platform.python_version(),
        process_id=os.getpid(),
        storage_total_gb=disk["storage_total_gb"],
        storage_used_gb=disk["storage_used_gb"],
        storage_free_gb=disk["storage_free_gb"],
        storage_percent=disk["storage_percent"],
        cache_status=app_cache.status(),
        recent_failed_ai_requests=failed_items,
        recent_app_errors=app_errors,
    )


async def run_system_diagnostics(
    db: AsyncSession,
    active_provider: str,
    active_model: str,
) -> SystemDiagnosticsResponse:
    """Run live, read-only operational diagnostics with measured latencies."""
    checks: List[DiagnosticCheckItem] = []

    t0 = time.perf_counter()
    db_ok = True
    try:
        await db.execute(text("SELECT 1"))
        db_lat = round((time.perf_counter() - t0) * 1000.0, 2)
        checks.append(
            DiagnosticCheckItem(
                name="Database Connectivity",
                status="pass",
                latency_ms=db_lat,
                detail="SELECT 1 succeeded.",
            )
        )
    except Exception as exc:
        db_ok = False
        checks.append(
            DiagnosticCheckItem(
                name="Database Connectivity",
                status="fail",
                latency_ms=None,
                detail=f"Database probe failed: {str(exc)[:140]}",
            )
        )

    if db_ok:
        try:
            intel = (
                await db.execute(
                    select(SystemAIConfig).where(SystemAIConfig.config_key == "default")
                )
            ).scalar_one_or_none()
            checks.append(
                DiagnosticCheckItem(
                    name="Intelligence Core Config",
                    status="pass" if intel else "warn",
                    latency_ms=None,
                    detail=f"Active {intel.active_provider}:{intel.active_model}" if intel else "Not yet initialized.",
                )
            )
        except Exception as exc:
            checks.append(
                DiagnosticCheckItem(
                    name="Intelligence Core Config",
                    status="fail",
                    latency_ms=None,
                    detail=str(exc)[:140],
                )
            )

        try:
            pcfg = (
                await db.execute(select(PlatformConfig).where(PlatformConfig.config_key == "default"))
            ).scalar_one_or_none()
            checks.append(
                DiagnosticCheckItem(
                    name="Platform Governance Policy",
                    status="pass" if pcfg else "warn",
                    latency_ms=None,
                    detail=(
                        f"maintenance_mode={'ON' if pcfg.maintenance_mode else 'OFF'}, "
                        f"signup={'OPEN' if pcfg.allow_public_registration else 'CLOSED'}"
                        if pcfg
                        else "Not yet initialized."
                    ),
                )
            )
        except Exception as exc:
            checks.append(
                DiagnosticCheckItem(
                    name="Platform Governance Policy",
                    status="fail",
                    latency_ms=None,
                    detail=str(exc)[:140],
                )
            )

    p0 = time.perf_counter()
    try:
        provider = ProviderFactory.get_provider(active_provider)
        p_health = await asyncio.wait_for(provider.check_health(), timeout=6.0)
        p_lat = round((time.perf_counter() - p0) * 1000.0, 2)
        if p_health.status == "healthy":
            models_cnt = len(p_health.available_models or [])
            checks.append(
                DiagnosticCheckItem(
                    name=f"AI Provider ({active_provider})",
                    status="pass",
                    latency_ms=p_lat,
                    detail=f"Healthy ({models_cnt} model(s) visible; target={active_model}).",
                )
            )
        else:
            checks.append(
                DiagnosticCheckItem(
                    name=f"AI Provider ({active_provider})",
                    status="warn",
                    latency_ms=p_lat,
                    detail=p_health.error_message or f"Provider status: {p_health.status}",
                )
            )
    except Exception as exc:
        checks.append(
            DiagnosticCheckItem(
                name=f"AI Provider ({active_provider})",
                status="warn",
                latency_ms=None,
                detail=f"Provider probe unreachable: {str(exc)[:140]}",
            )
        )

    disk = _read_disk_usage()
    free_gb = disk.get("storage_free_gb")
    if free_gb is None:
        checks.append(
            DiagnosticCheckItem(
                name="Host Storage",
                status="warn",
                latency_ms=None,
                detail="Disk usage telemetry unavailable.",
            )
        )
    else:
        disk_status = "pass" if free_gb >= 1.0 else "warn"
        checks.append(
            DiagnosticCheckItem(
                name="Host Storage",
                status=disk_status,
                latency_ms=None,
                detail=f"{free_gb} GB free of {disk['storage_total_gb']} GB ({disk['storage_percent']}% used).",
            )
        )

    cache_info = app_cache.status()
    checks.append(
        DiagnosticCheckItem(
            name="Control Centre Cache",
            status="pass",
            latency_ms=None,
            detail=f"{cache_info['entries']}/{cache_info['max_entries']} active cached entries.",
        )
    )

    statuses = {c.status for c in checks}
    overall = "fail" if "fail" in statuses else ("warn" if "warn" in statuses else "pass")
    host_scope = "Measurements reflect the backend API server process and its attached host/container filesystem."

    return SystemDiagnosticsResponse(
        checked_at=datetime.now(timezone.utc),
        overall_status=overall,
        host_scope_note=host_scope,
        checks=checks,
    )


async def test_ai_model_connection(
    provider_name: str,
    model_name: str,
    prompt: str = "Respond concisely with the word OK.",
) -> AITestResponse:
    """Execute a real, bounded connectivity test against the requested provider & model."""
    provider = ProviderFactory.get_provider(provider_name)
    started = time.perf_counter()
    tokens: List[str] = []
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    error_message: Optional[str] = None
    success = True

    async def _run_probe() -> None:
        nonlocal prompt_tokens, completion_tokens, total_tokens, error_message, success
        messages = [{"role": "user", "content": prompt}]
        async for event in provider.stream_chat_with_metrics(
            messages=messages,
            model=model_name,
            temperature=0.0,
            context_window=1024,
        ):
            etype = event.get("type")
            if etype == "token":
                tokens.append(str(event.get("text") or ""))
                if sum(len(t) for t in tokens) >= 240:
                    break
            elif etype == "done":
                prompt_tokens = event.get("prompt_tokens")
                completion_tokens = event.get("completion_tokens")
                total_tokens = event.get("total_tokens")
            elif etype == "error":
                success = False
                error_message = str(event.get("message") or "AI test failed")[:300]
                break

    try:
        await asyncio.wait_for(_run_probe(), timeout=20.0)
        preview = "".join(tokens).strip()[:240]
        if success and not preview and not error_message:
            # Some test/custom BaseAIProvider subclasses only implement complete_chat meaningfully
            fallback_text = await asyncio.wait_for(
                provider.complete_chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=model_name,
                    temperature=0.0,
                    context_window=1024,
                ),
                timeout=15.0,
            )
            preview = (fallback_text or "").strip()[:240]
    except asyncio.TimeoutError:
        success = False
        error_message = "AI connectivity test timed out after 20 seconds."
        preview = None
    except Exception as exc:
        success = False
        error_message = str(exc)[:300]
        preview = None

    latency_ms = max(1, int((time.perf_counter() - started) * 1000))
    return AITestResponse(
        provider=provider.name,
        model=model_name,
        success=success,
        latency_ms=latency_ms,
        response_preview=preview if success else None,
        error_message=error_message,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        checked_at=datetime.now(timezone.utc),
    )
