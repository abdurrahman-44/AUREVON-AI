import React from 'react';
import { Cpu, Server, Terminal } from 'lucide-react';
import { AdminAnalyticsResponse, AdminSectionRoute } from '../../types';
import { MetricTile } from './AdminLayout';
import { ModelUtilizationChart, StackedBarChart, TimeSeriesLineChart } from './AnalyticsCharts';

interface AdminDashboardPageProps {
  analytics: AdminAnalyticsResponse | null;
  range: '24h' | '7d' | '30d' | '90d' | 'custom';
  onChangeRange: (next: '24h' | '7d' | '30d' | '90d' | 'custom') => void;
  customStart: string;
  customEnd: string;
  onChangeCustomStart: (val: string) => void;
  onChangeCustomEnd: (val: string) => void;
  onApplyCustomRange: () => void;
  onNavigate: (route: AdminSectionRoute) => void;
}

const fmtMetric = (val: number | null | undefined, suffix = ''): string => {
  if (val === null || val === undefined) return 'Unavailable';
  return `${val}${suffix}`;
};

export const AdminDashboardPage: React.FC<AdminDashboardPageProps> = ({
  analytics,
  range,
  onChangeRange,
  customStart,
  customEnd,
  onChangeCustomStart,
  onChangeCustomEnd,
  onApplyCustomRange,
  onNavigate,
}) => {
  const ov = analytics?.overview;
  const perf = analytics?.performance;

  return (
    <div className="space-y-6">
      {/* Filter Toolbar & Quick Jumps */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-surface px-4 py-3">
        <div className="flex flex-wrap items-center gap-1.5">
          {(['24h', '7d', '30d', '90d', 'custom'] as const).map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => onChangeRange(r)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                range === r
                  ? 'bg-accent text-white shadow-sm'
                  : 'bg-elevated text-ink-secondary hover:text-ink'
              }`}
            >
              {r === 'custom' ? 'Custom' : r.toUpperCase()}
            </button>
          ))}
          {range === 'custom' && (
            <div className="flex flex-wrap items-center gap-2 ml-2">
              <input
                type="date"
                value={customStart}
                onChange={(e) => onChangeCustomStart(e.target.value)}
                className="rounded-lg border border-line bg-elevated px-2.5 py-1 text-xs text-ink"
              />
              <span className="text-xs text-ink-muted">to</span>
              <input
                type="date"
                value={customEnd}
                onChange={(e) => onChangeCustomEnd(e.target.value)}
                className="rounded-lg border border-line bg-elevated px-2.5 py-1 text-xs text-ink"
              />
              <button
                type="button"
                onClick={onApplyCustomRange}
                className="rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white hover:bg-accent-hover transition"
              >
                Apply
              </button>
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => onNavigate('/admin/terminal')}
            className="flex items-center gap-1.5 rounded-lg border border-line bg-elevated px-3 py-1.5 text-xs font-medium text-ink hover:border-accent/50 transition"
          >
            <Terminal className="h-3.5 w-3.5 text-accent" />
            Open Terminal
          </button>
          <button
            type="button"
            onClick={() => onNavigate('/admin/ai')}
            className="flex items-center gap-1.5 rounded-lg border border-line bg-elevated px-3 py-1.5 text-xs font-medium text-ink hover:border-accent/50 transition"
          >
            <Cpu className="h-3.5 w-3.5 text-accent" />
            Test AI
          </button>
          <button
            type="button"
            onClick={() => onNavigate('/admin/system')}
            className="flex items-center gap-1.5 rounded-lg border border-line bg-elevated px-3 py-1.5 text-xs font-medium text-ink hover:border-accent/50 transition"
          >
            <Server className="h-3.5 w-3.5 text-accent" />
            Diagnostics
          </button>
        </div>
      </div>

      {/* Primary KPI Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricTile
          label="Registered Users"
          value={ov?.total_users ?? 0}
          sublabel={`${ov?.new_users ?? 0} new in ${analytics?.range_label || range} • ${ov?.active_users_24h ?? 0} active (24h)`}
        />
        <MetricTile
          label="AI Requests (Window)"
          value={ov?.total_ai_requests ?? 0}
          sublabel={`${ov?.requests_today ?? 0} today UTC • ${ov?.successful_requests ?? 0} ok / ${ov?.failed_requests ?? 0} fail`}
        />
        <MetricTile
          label="Success Rate"
          value={ov?.success_rate_pct !== null && ov?.success_rate_pct !== undefined ? `${ov.success_rate_pct}%` : 'Unavailable'}
          sublabel={`${ov?.total_conversations ?? 0} total conversations`}
          tone={
            ov?.success_rate_pct === null || ov?.success_rate_pct === undefined
              ? 'default'
              : ov.success_rate_pct >= 95
                ? 'good'
                : ov.success_rate_pct >= 80
                  ? 'warn'
                  : 'bad'
          }
        />
        <MetricTile
          label="Latency (Avg / P95)"
          value={
            perf?.avg_latency_ms !== null && perf?.avg_latency_ms !== undefined
              ? `${perf.avg_latency_ms} ms`
              : 'Unavailable'
          }
          sublabel={`Median ${fmtMetric(perf?.median_latency_ms, ' ms')} • P95 ${fmtMetric(perf?.p95_latency_ms, ' ms')}`}
        />
      </div>

      {/* Secondary Performance & Token Strip */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricTile
          label="Time To First Token"
          value={fmtMetric(perf?.avg_first_token_ms, ' ms')}
          sublabel="Measured first-chunk latency"
        />
        <MetricTile
          label="Total Tokens Consumed"
          value={perf?.total_tokens !== null && perf?.total_tokens !== undefined ? perf.total_tokens.toLocaleString() : 'Unavailable'}
          sublabel={`Prompt ${perf?.prompt_tokens?.toLocaleString() ?? 'Unavailable'} / Completion ${perf?.completion_tokens?.toLocaleString() ?? 'Unavailable'}`}
        />
        <MetricTile
          label="Throughput"
          value={fmtMetric(perf?.requests_per_day, ' req/d')}
          sublabel={`${fmtMetric(perf?.requests_per_minute, ' req/min')} average`}
        />
        <MetricTile
          label="Active Cohorts"
          value={`${ov?.active_users_7d ?? 0} (7d)`}
          sublabel={`${ov?.active_users_30d ?? 0} active in last 30 days`}
        />
      </div>

      {/* Real Time-Series Charts */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <StackedBarChart
          title="Request Volume & Outcomes"
          subtitle="Successful vs failed AI inferences per bucket"
          data={analytics?.time_series || []}
          primaryKey="successful_requests"
          primaryLabel="Successful"
          primaryColor="#10b981"
          secondaryKey="failed_requests"
          secondaryLabel="Failed"
          secondaryColor="#f43f5e"
        />
        <StackedBarChart
          title="Token Consumption"
          subtitle="Prompt vs completion tokens reported by providers"
          data={analytics?.time_series || []}
          primaryKey="prompt_tokens"
          primaryLabel="Prompt Tokens"
          primaryColor="#6366f1"
          secondaryKey="completion_tokens"
          secondaryLabel="Completion Tokens"
          secondaryColor="#22d3ee"
        />
        <TimeSeriesLineChart
          title="Average Response Latency"
          subtitle="End-to-end duration in milliseconds"
          data={analytics?.time_series || []}
          unit="ms"
          series={[
            { key: 'avg_latency_ms', label: 'Avg Latency', color: '#f59e0b' },
          ]}
        />
        <TimeSeriesLineChart
          title="User Activity & Signups"
          subtitle="Distinct active users & new registrations per interval"
          data={analytics?.time_series || []}
          series={[
            { key: 'active_users', label: 'Active Users', color: '#8b5cf6' },
            { key: 'new_users', label: 'New Users', color: '#10b981' },
          ]}
        />
      </div>

      {/* Model Utilization & Errors */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ModelUtilizationChart items={analytics?.model_utilization || []} />
        <div className="rounded-xl border border-line bg-surface p-4">
          <h3 className="text-sm font-semibold text-ink">Error Categories Breakdown</h3>
          <p className="mt-0.5 text-xs text-ink-muted">Observed failure classes in selected date range</p>
          <div className="mt-4 space-y-2">
            {(analytics?.error_breakdown || []).length === 0 ? (
              <p className="text-xs text-ink-muted py-6 text-center">No failed AI requests recorded in this range.</p>
            ) : (
              analytics!.error_breakdown.map((errItem) => (
                <div
                  key={errItem.error_category}
                  className="flex items-center justify-between rounded-lg border border-line bg-elevated/60 px-3 py-2 text-xs"
                >
                  <span className="font-mono text-ink">{errItem.error_category}</span>
                  <span className="rounded bg-rose-500/15 px-2 py-0.5 font-semibold text-rose-500">
                    {errItem.count}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
