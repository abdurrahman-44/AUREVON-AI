import React, { useState } from 'react';
import { DailyTimeSeriesPoint, ModelUtilizationItem } from '../../types';

interface LineSeriesConfig {
  key: keyof DailyTimeSeriesPoint;
  label: string;
  color: string;
}

interface LineChartProps {
  title: string;
  subtitle?: string;
  data: DailyTimeSeriesPoint[];
  series: LineSeriesConfig[];
  unit?: string;
  emptyMessage?: string;
}

function formatAxisLabel(raw: string): string {
  if (raw.includes(' ')) {
    // hourly: YYYY-MM-DD HH:00 -> HH:00
    return raw.split(' ')[1];
  }
  // daily: YYYY-MM-DD -> MM/DD
  const parts = raw.split('-');
  return parts.length === 3 ? `${parts[1]}/${parts[2]}` : raw;
}

export const TimeSeriesLineChart: React.FC<LineChartProps> = ({
  title,
  subtitle,
  data,
  series,
  unit = '',
  emptyMessage = 'No telemetry recorded in this window.',
}) => {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const hasAnyValue = data.some((pt) =>
    series.some((s) => {
      const v = pt[s.key];
      return typeof v === 'number' && v > 0;
    })
  );

  const allValues: number[] = [];
  for (const pt of data) {
    for (const s of series) {
      const v = pt[s.key];
      if (typeof v === 'number' && Number.isFinite(v)) {
        allValues.push(v);
      }
    }
  }

  const maxVal = allValues.length > 0 ? Math.max(...allValues, 1) : 1;
  const W = 520;
  const H = 190;
  const PAD_L = 42;
  const PAD_R = 14;
  const PAD_T = 16;
  const PAD_B = 28;
  const plotW = W - PAD_L - PAD_R;
  const plotH = H - PAD_T - PAD_B;

  const getX = (i: number) =>
    data.length <= 1 ? PAD_L + plotW / 2 : PAD_L + (i / (data.length - 1)) * plotW;
  const getY = (val: number) => PAD_T + plotH - (val / maxVal) * plotH;

  const yTicks = [0, 0.5, 1].map((t) => ({
    y: PAD_T + plotH - t * plotH,
    val: Math.round(maxVal * t * 10) / 10,
  }));

  const labelStep = Math.max(1, Math.ceil(data.length / 6));

  return (
    <div className="rounded-xl border border-line bg-surface p-4 flex flex-col">
      <div className="flex items-start justify-between gap-2 mb-3">
        <div>
          <h4 className="text-sm font-medium text-ink">{title}</h4>
          {subtitle && <p className="text-xs text-ink-muted mt-0.5">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-3 text-[11px] text-ink-secondary">
          {series.map((s) => (
            <span key={String(s.key)} className="inline-flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color }} />
              {s.label}
            </span>
          ))}
        </div>
      </div>

      {data.length === 0 || !hasAnyValue ? (
        <div className="h-[190px] flex items-center justify-center text-xs text-ink-muted border border-dashed border-line rounded-lg">
          {emptyMessage}
        </div>
      ) : (
        <div className="relative">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-[190px] overflow-visible">
            {yTicks.map((t, idx) => (
              <g key={idx}>
                <line
                  x1={PAD_L}
                  y1={t.y}
                  x2={W - PAD_R}
                  y2={t.y}
                  stroke="currentColor"
                  className="text-line"
                  strokeDasharray="3 3"
                  strokeWidth={1}
                />
                <text
                  x={PAD_L - 6}
                  y={t.y + 3}
                  textAnchor="end"
                  className="fill-ink-muted text-[10px] font-mono"
                >
                  {t.val}
                </text>
              </g>
            ))}

            {series.map((s) => {
              const pts: { x: number; y: number; val: number; idx: number }[] = [];
              data.forEach((pt, idx) => {
                const raw = pt[s.key];
                if (typeof raw === 'number' && Number.isFinite(raw)) {
                  pts.push({ x: getX(idx), y: getY(raw), val: raw, idx });
                }
              });

              const pathD = pts
                .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
                .join(' ');

              return (
                <g key={String(s.key)}>
                  {pts.length > 1 && (
                    <path
                      d={pathD}
                      fill="none"
                      stroke={s.color}
                      strokeWidth={2}
                      strokeLinejoin="round"
                      strokeLinecap="round"
                    />
                  )}
                  {pts.map((p) => (
                    <circle
                      key={p.idx}
                      cx={p.x}
                      cy={p.y}
                      r={hoverIdx === p.idx ? 4.5 : 2.5}
                      fill={s.color}
                      className="cursor-pointer transition-all"
                      onMouseEnter={() => setHoverIdx(p.idx)}
                      onMouseLeave={() => setHoverIdx(null)}
                    />
                  ))}
                </g>
              );
            })}

            {data.map((pt, idx) => {
              if (idx % labelStep !== 0 && idx !== data.length - 1) return null;
              return (
                <text
                  key={pt.date}
                  x={getX(idx)}
                  y={H - 6}
                  textAnchor="middle"
                  className="fill-ink-muted text-[10px] font-mono"
                >
                  {formatAxisLabel(pt.date)}
                </text>
              );
            })}
          </svg>

          {hoverIdx !== null && data[hoverIdx] && (
            <div className="absolute top-1 right-1 rounded-lg border border-line bg-canvas/95 px-2.5 py-1.5 text-[11px] shadow-sm pointer-events-none">
              <div className="font-mono text-ink-muted mb-0.5">{data[hoverIdx].date}</div>
              {series.map((s) => {
                const val = data[hoverIdx][s.key];
                return (
                  <div key={String(s.key)} className="flex items-center justify-between gap-3">
                    <span className="text-ink-secondary">{s.label}:</span>
                    <span className="font-mono font-medium text-ink">
                      {typeof val === 'number' ? `${val}${unit}` : 'N/A'}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

interface StackedBarChartProps {
  title: string;
  subtitle?: string;
  data: DailyTimeSeriesPoint[];
  primaryKey: keyof DailyTimeSeriesPoint;
  primaryLabel: string;
  primaryColor: string;
  secondaryKey: keyof DailyTimeSeriesPoint;
  secondaryLabel: string;
  secondaryColor: string;
  emptyMessage?: string;
}

export const StackedBarChart: React.FC<StackedBarChartProps> = ({
  title,
  subtitle,
  data,
  primaryKey,
  primaryLabel,
  primaryColor,
  secondaryKey,
  secondaryLabel,
  secondaryColor,
  emptyMessage = 'No data available in this period.',
}) => {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const totals = data.map((d) => {
    const a = Number(d[primaryKey] || 0);
    const b = Number(d[secondaryKey] || 0);
    return { a, b, sum: a + b };
  });

  const maxSum = Math.max(...totals.map((t) => t.sum), 1);
  const hasData = totals.some((t) => t.sum > 0);

  const W = 520;
  const H = 190;
  const PAD_L = 44;
  const PAD_R = 12;
  const PAD_T = 16;
  const PAD_B = 28;
  const plotW = W - PAD_L - PAD_R;
  const plotH = H - PAD_T - PAD_B;
  const barStep = data.length > 0 ? plotW / data.length : plotW;
  const barW = Math.max(4, Math.min(26, barStep * 0.62));
  const labelStep = Math.max(1, Math.ceil(data.length / 6));

  return (
    <div className="rounded-xl border border-line bg-surface p-4 flex flex-col">
      <div className="flex items-start justify-between gap-2 mb-3">
        <div>
          <h4 className="text-sm font-medium text-ink">{title}</h4>
          {subtitle && <p className="text-xs text-ink-muted mt-0.5">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-3 text-[11px] text-ink-secondary">
          <span className="inline-flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm" style={{ backgroundColor: primaryColor }} />
            {primaryLabel}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm" style={{ backgroundColor: secondaryColor }} />
            {secondaryLabel}
          </span>
        </div>
      </div>

      {data.length === 0 || !hasData ? (
        <div className="h-[190px] flex items-center justify-center text-xs text-ink-muted border border-dashed border-line rounded-lg">
          {emptyMessage}
        </div>
      ) : (
        <div className="relative">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-[190px] overflow-visible">
            {[0, 0.5, 1].map((t, idx) => {
              const y = PAD_T + plotH - t * plotH;
              const val = Math.round(maxSum * t);
              return (
                <g key={idx}>
                  <line
                    x1={PAD_L}
                    y1={y}
                    x2={W - PAD_R}
                    y2={y}
                    stroke="currentColor"
                    className="text-line"
                    strokeDasharray="3 3"
                    strokeWidth={1}
                  />
                  <text x={PAD_L - 6} y={y + 3} textAnchor="end" className="fill-ink-muted text-[10px] font-mono">
                    {val >= 1000 ? `${(val / 1000).toFixed(1)}k` : val}
                  </text>
                </g>
              );
            })}

            {data.map((pt, idx) => {
              const { a, b } = totals[idx];
              const hA = (a / maxSum) * plotH;
              const hB = (b / maxSum) * plotH;
              const x = PAD_L + idx * barStep + (barStep - barW) / 2;
              const yB = PAD_T + plotH - hB;
              const yA = yB - hA;

              return (
                <g
                  key={pt.date}
                  onMouseEnter={() => setHoverIdx(idx)}
                  onMouseLeave={() => setHoverIdx(null)}
                  className="cursor-pointer"
                >
                  {b > 0 && <rect x={x} y={yB} width={barW} height={hB} fill={secondaryColor} rx={2} />}
                  {a > 0 && <rect x={x} y={yA} width={barW} height={hA} fill={primaryColor} rx={2} />}
                  {(idx % labelStep === 0 || idx === data.length - 1) && (
                    <text
                      x={x + barW / 2}
                      y={H - 6}
                      textAnchor="middle"
                      className="fill-ink-muted text-[10px] font-mono"
                    >
                      {formatAxisLabel(pt.date)}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>

          {hoverIdx !== null && data[hoverIdx] && (
            <div className="absolute top-1 right-1 rounded-lg border border-line bg-canvas/95 px-2.5 py-1.5 text-[11px] shadow-sm pointer-events-none">
              <div className="font-mono text-ink-muted mb-0.5">{data[hoverIdx].date}</div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-ink-secondary">{primaryLabel}:</span>
                <span className="font-mono font-medium text-ink">{totals[hoverIdx].a.toLocaleString()}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-ink-secondary">{secondaryLabel}:</span>
                <span className="font-mono font-medium text-ink">{totals[hoverIdx].b.toLocaleString()}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

interface ModelUtilizationChartProps {
  items: ModelUtilizationItem[];
}

export const ModelUtilizationChart: React.FC<ModelUtilizationChartProps> = ({ items }) => {
  const totalRequests = items.reduce((acc, m) => acc + m.request_count, 0);

  return (
    <div className="rounded-xl border border-line bg-surface p-4 flex flex-col">
      <div className="mb-3">
        <h4 className="text-sm font-medium text-ink">Model Utilization Breakdown</h4>
        <p className="text-xs text-ink-muted mt-0.5">Actual logged requests grouped by provider & model</p>
      </div>

      {items.length === 0 ? (
        <div className="h-[190px] flex items-center justify-center text-xs text-ink-muted border border-dashed border-line rounded-lg">
          No AI model requests recorded in this range.
        </div>
      ) : (
        <div className="space-y-3 overflow-y-auto max-h-[190px] pr-1">
          {items.map((item) => {
            const pct = totalRequests > 0 ? Math.round((item.request_count / totalRequests) * 100) : 0;
            return (
              <div key={`${item.provider}-${item.model}`} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="font-mono font-medium text-ink truncate">{item.model}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-elevated text-ink-secondary uppercase">
                      {item.provider}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 font-mono text-[11px] text-ink-secondary shrink-0">
                    <span>{item.request_count} req ({pct}%)</span>
                    <span>{item.avg_latency_ms !== null ? `${item.avg_latency_ms}ms` : 'N/A'}</span>
                  </div>
                </div>
                <div className="w-full h-2 rounded-full bg-elevated overflow-hidden">
                  <div
                    className="h-full rounded-full bg-accent transition-all"
                    style={{ width: `${Math.max(4, pct)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
