import React, { useState } from 'react';
import { Activity, AlertTriangle, CheckCircle2, HardDrive, Play, Server, XCircle } from 'lucide-react';
import { fetchAdminDiagnostics } from '../../services/api';
import { SystemDiagnosticsResponse, SystemMonitoringResponse } from '../../types';
import { MetricTile } from './AdminLayout';

interface AdminSystemPageProps {
  monitoring: SystemMonitoringResponse | null;
  onError: (msg: string) => void;
}

function formatUptime(seconds?: number | null): string {
  if (seconds === null || seconds === undefined) return 'Unavailable';
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const parts: string[] = [];
  if (d) parts.push(`${d}d`);
  if (h || d) parts.push(`${h}h`);
  if (m || h || d) parts.push(`${m}m`);
  parts.push(`${s}s`);
  return parts.join(' ');
}

export const AdminSystemPage: React.FC<AdminSystemPageProps> = ({ monitoring, onError }) => {
  const [diagnostics, setDiagnostics] = useState<SystemDiagnosticsResponse | null>(null);
  const [runningDiag, setRunningDiag] = useState(false);

  const handleRunDiagnostics = async () => {
    setRunningDiag(true);
    try {
      const res = await fetchAdminDiagnostics();
      setDiagnostics(res);
    } catch (err: any) {
      onError(err.message || 'Diagnostics run failed');
    } finally {
      setRunningDiag(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-line bg-surface px-4 py-3 text-xs text-ink-secondary flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Server className="h-4 w-4 text-accent shrink-0" />
          <span>
            Host Scope: Telemetry reflects the running backend API server process (
            <strong className="text-ink">{monitoring?.host_environment || 'backend_host'}</strong> •{' '}
            {monitoring?.os_platform || 'OS Unavailable'} • Python {monitoring?.python_version || 'Unavailable'}).
          </span>
        </div>
        <span className="font-mono text-[11px] text-ink-muted">
          PID: {monitoring?.process_id ?? 'Unavailable'}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricTile
          label="Backend & Database"
          value={monitoring ? monitoring.backend_status.toUpperCase() : 'Unavailable'}
          sublabel={
            monitoring
              ? `DB: ${monitoring.database_connected ? 'Connected' : 'Disconnected'} (${monitoring.database_dialect})`
              : undefined
          }
          tone={monitoring?.database_connected ? 'good' : 'bad'}
        />
        <MetricTile
          label="Process Uptime"
          value={formatUptime(monitoring?.uptime_seconds)}
          sublabel={
            monitoring?.process_rss_mb !== null && monitoring?.process_rss_mb !== undefined
              ? `Process RSS: ${monitoring.process_rss_mb} MB`
              : 'Process RSS: Unavailable'
          }
        />
        <MetricTile
          label="Host CPU & Memory"
          value={
            monitoring?.cpu_percent !== null && monitoring?.cpu_percent !== undefined
              ? `${monitoring.cpu_percent}% CPU`
              : 'Unavailable'
          }
          sublabel={
            monitoring?.ram_percent !== null && monitoring?.ram_percent !== undefined
              ? `RAM ${monitoring.ram_used_mb} / ${monitoring.ram_total_mb} MB (${monitoring.ram_percent}%)`
              : 'RAM: Unavailable'
          }
        />
        <MetricTile
          label="Host Disk Storage"
          value={
            monitoring?.storage_percent !== null && monitoring?.storage_percent !== undefined
              ? `${monitoring.storage_percent}% Used`
              : 'Unavailable'
          }
          sublabel={
            monitoring?.storage_free_gb !== null && monitoring?.storage_free_gb !== undefined
              ? `${monitoring.storage_free_gb} GB free of ${monitoring.storage_total_gb} GB`
              : 'Storage stats unavailable'
          }
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <section className="rounded-xl border border-line bg-surface p-5 lg:col-span-7 space-y-3">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-accent" />
            <h2 className="text-sm font-semibold text-ink">AI Provider Connectivity Matrix</h2>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {(monitoring?.provider_health || []).map((ph) => (
              <div
                key={ph.provider}
                className="rounded-lg border border-line bg-elevated/50 p-3 text-xs space-y-1"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold capitalize text-ink">{ph.provider}</span>
                  <span
                    className={`rounded px-2 py-0.5 text-[10px] font-semibold ${
                      ph.available
                        ? 'bg-emerald-500/15 text-emerald-500'
                        : 'bg-amber-500/15 text-amber-500'
                    }`}
                  >
                    {ph.available ? 'Reachable' : 'Unreachable'}
                  </span>
                </div>
                <div className="text-[11px] text-ink-secondary">Visible Models: {ph.models_count}</div>
                {ph.error && <div className="truncate text-[11px] text-rose-400">{ph.error}</div>}
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-xl border border-line bg-surface p-5 lg:col-span-5 space-y-3">
          <div className="flex items-center gap-2">
            <HardDrive className="h-4 w-4 text-accent" />
            <h2 className="text-sm font-semibold text-ink">Control Centre TTL Cache</h2>
          </div>
          <div className="rounded-lg border border-line bg-elevated/50 p-4 text-xs space-y-2">
            <div className="flex justify-between">
              <span className="text-ink-muted">Active Cache Entries</span>
              <span className="font-semibold text-ink">
                {monitoring?.cache_status
                  ? `${monitoring.cache_status.entries} / ${monitoring.cache_status.max_entries}`
                  : 'Unavailable'}
              </span>
            </div>
            <div>
              <div className="text-ink-muted mb-1">Active Keys</div>
              <div className="flex flex-wrap gap-1.5">
                {monitoring?.cache_status?.keys && monitoring.cache_status.keys.length > 0 ? (
                  monitoring.cache_status.keys.map((k) => (
                    <span
                      key={k}
                      className="rounded bg-surface border border-line px-2 py-0.5 font-mono text-[10px] text-ink"
                    >
                      {k}
                    </span>
                  ))
                ) : (
                  <span className="text-[11px] text-ink-muted">Empty (no active entries)</span>
                )}
              </div>
            </div>
          </div>
        </section>
      </div>

      <section className="rounded-xl border border-line bg-surface p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-ink">Operational Diagnostics Runner</h2>
            <p className="text-xs text-ink-muted">
              Runs live read-only checks against SQLite/Postgres, config records, active AI provider, host disk, and cache.
            </p>
          </div>
          <button
            type="button"
            onClick={handleRunDiagnostics}
            disabled={runningDiag}
            className="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50 transition"
          >
            <Play className="h-3.5 w-3.5" />
            {runningDiag ? 'Running Checks...' : 'Run System Diagnostics'}
          </button>
        </div>

        {diagnostics && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <span className="text-ink-secondary">{diagnostics.host_scope_note}</span>
              <span
                className={`rounded px-2.5 py-0.5 font-semibold uppercase ${
                  diagnostics.overall_status === 'pass'
                    ? 'bg-emerald-500/15 text-emerald-500'
                    : diagnostics.overall_status === 'warn'
                      ? 'bg-amber-500/15 text-amber-500'
                      : 'bg-rose-500/15 text-rose-500'
                }`}
              >
                Overall: {diagnostics.overall_status}
              </span>
            </div>

            <div className="grid grid-cols-1 gap-2.5 md:grid-cols-2">
              {diagnostics.checks.map((c) => (
                <div
                  key={c.name}
                  className="flex items-start gap-2.5 rounded-lg border border-line bg-elevated/50 p-3 text-xs"
                >
                  {c.status === 'pass' ? (
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                  ) : c.status === 'warn' ? (
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
                  ) : (
                    <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-500" />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-ink">{c.name}</span>
                      {c.latency_ms !== null && c.latency_ms !== undefined && (
                        <span className="font-mono text-[11px] text-ink-muted">{c.latency_ms} ms</span>
                      )}
                    </div>
                    <p className="mt-0.5 text-[11px] text-ink-secondary">{c.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
};
