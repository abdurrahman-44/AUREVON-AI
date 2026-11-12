import React, { useEffect, useState } from 'react';
import { Trash2 } from 'lucide-react';
import {
  fetchAdminAuditLogs,
  fetchApiRequestLogs,
  fetchRecentErrorLogs,
  pruneOperationalLogs,
} from '../../services/api';
import {
  ErrorLogsResponse,
  PaginatedAPIRequestLogsResponse,
  PaginatedAdminAuditLogsResponse,
} from '../../types';

interface AdminLogsPageProps {
  onNotice: (msg: string) => void;
  onError: (msg: string) => void;
}

type LogSubTab = 'requests' | 'audit' | 'errors';

export const AdminLogsPage: React.FC<AdminLogsPageProps> = ({ onNotice, onError }) => {
  const [tab, setTab] = useState<LogSubTab>('requests');

  const [reqLogs, setReqLogs] = useState<PaginatedAPIRequestLogsResponse | null>(null);
  const [reqPage, setReqPage] = useState(1);
  const [reqMethod, setReqMethod] = useState('');
  const [reqStatus, setReqStatus] = useState('');
  const [reqPath, setReqPath] = useState('');

  const [auditLogs, setAuditLogs] = useState<PaginatedAdminAuditLogsResponse | null>(null);
  const [auditPage, setAuditPage] = useState(1);
  const [auditSearch, setAuditSearch] = useState('');
  const [auditStatus, setAuditStatus] = useState('');

  const [errLogs, setErrLogs] = useState<ErrorLogsResponse | null>(null);

  const [pruneDays, setPruneDays] = useState(30);
  const [pruning, setPruning] = useState(false);

  const loadRequests = async () => {
    try {
      const data = await fetchApiRequestLogs({
        page: reqPage,
        pageSize: 20,
        method: reqMethod || undefined,
        statusCode: reqStatus ? Number(reqStatus) : undefined,
        pathSearch: reqPath || undefined,
      });
      setReqLogs(data);
    } catch (err: any) {
      onError(err.message || 'Failed to load API logs');
    }
  };

  const loadAudit = async () => {
    try {
      const data = await fetchAdminAuditLogs({
        page: auditPage,
        pageSize: 20,
        search: auditSearch || undefined,
        statusFilter: auditStatus || undefined,
      });
      setAuditLogs(data);
    } catch (err: any) {
      onError(err.message || 'Failed to load audit logs');
    }
  };

  const loadErrors = async () => {
    try {
      const data = await fetchRecentErrorLogs();
      setErrLogs(data);
    } catch (err: any) {
      onError(err.message || 'Failed to load error logs');
    }
  };

  useEffect(() => {
    if (tab === 'requests') loadRequests();
    if (tab === 'audit') loadAudit();
    if (tab === 'errors') loadErrors();
  }, [tab, reqPage, reqMethod, reqStatus, reqPath, auditPage, auditSearch, auditStatus]);

  const handlePrune = async () => {
    setPruning(true);
    try {
      const res = await pruneOperationalLogs(pruneDays);
      const totalDeleted = Object.values(res.deleted).reduce((acc, v) => acc + v, 0);
      onNotice(`Pruned ${totalDeleted} telemetry record(s) older than ${res.retention_days} day(s).`);
      if (tab === 'requests') loadRequests();
      if (tab === 'audit') loadAudit();
      if (tab === 'errors') loadErrors();
    } catch (err: any) {
      onError(err.message || 'Log pruning failed');
    } finally {
      setPruning(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-surface px-4 py-3">
        <div className="flex flex-wrap items-center gap-1.5">
          {(
            [
              { id: 'requests', label: 'HTTP API Requests' },
              { id: 'audit', label: 'Owner Audit Trail' },
              { id: 'errors', label: 'AI & Backend Errors' },
            ] as const
          ).map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                tab === t.id ? 'bg-accent text-white' : 'bg-elevated text-ink-secondary hover:text-ink'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="text-ink-muted">Retention (days):</span>
          <input
            type="number"
            min={1}
            max={365}
            value={pruneDays}
            onChange={(e) => setPruneDays(Math.max(1, Number(e.target.value)))}
            className="w-16 rounded-lg border border-line bg-elevated px-2 py-1 text-xs text-ink"
          />
          <button
            type="button"
            onClick={handlePrune}
            disabled={pruning}
            className="flex items-center gap-1.5 rounded-lg border border-line bg-elevated px-3 py-1.5 text-xs font-medium text-ink hover:border-rose-500/50 disabled:opacity-50"
          >
            <Trash2 className="h-3.5 w-3.5 text-rose-500" />
            {pruning ? 'Pruning...' : 'Prune Old Logs'}
          </button>
        </div>
      </div>

      {tab === 'requests' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface p-3">
            <select
              value={reqMethod}
              onChange={(e) => {
                setReqMethod(e.target.value);
                setReqPage(1);
              }}
              className="rounded-lg border border-line bg-elevated px-3 py-1.5 text-xs text-ink"
            >
              <option value="">All Methods</option>
              <option value="GET">GET</option>
              <option value="POST">POST</option>
              <option value="PATCH">PATCH</option>
              <option value="DELETE">DELETE</option>
            </select>
            <input
              type="number"
              placeholder="Status (e.g. 200, 401, 503)"
              value={reqStatus}
              onChange={(e) => {
                setReqStatus(e.target.value);
                setReqPage(1);
              }}
              className="w-44 rounded-lg border border-line bg-elevated px-3 py-1.5 text-xs text-ink"
            />
            <input
              type="text"
              placeholder="Filter path (e.g. /api/chat)..."
              value={reqPath}
              onChange={(e) => {
                setReqPath(e.target.value);
                setReqPage(1);
              }}
              className="flex-1 min-w-[200px] rounded-lg border border-line bg-elevated px-3 py-1.5 text-xs text-ink"
            />
          </div>

          <div className="overflow-x-auto rounded-xl border border-line bg-surface">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-line bg-elevated/60 text-[11px] uppercase text-ink-muted">
                <tr>
                  <th className="px-4 py-2.5">Timestamp</th>
                  <th className="px-4 py-2.5">Method</th>
                  <th className="px-4 py-2.5">Path</th>
                  <th className="px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5 text-right">Duration</th>
                  <th className="px-4 py-2.5 text-right">Client IP</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line font-mono text-[11px]">
                {(reqLogs?.items || []).map((r) => (
                  <tr key={r.id} className="hover:bg-elevated/40">
                    <td className="px-4 py-2.5 text-ink-muted">{new Date(r.created_at).toLocaleString()}</td>
                    <td className="px-4 py-2.5 font-semibold text-accent">{r.method}</td>
                    <td className="px-4 py-2.5 text-ink">{r.path}</td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`rounded px-1.5 py-0.5 font-semibold ${
                          r.status_code < 400
                            ? 'bg-emerald-500/15 text-emerald-500'
                            : r.status_code < 500
                              ? 'bg-amber-500/15 text-amber-500'
                              : 'bg-rose-500/15 text-rose-500'
                        }`}
                      >
                        {r.status_code}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right text-ink-secondary">{r.duration_ms} ms</td>
                    <td className="px-4 py-2.5 text-right text-ink-muted">{r.client_ip || 'local'}</td>
                  </tr>
                ))}
                {(!reqLogs || reqLogs.items.length === 0) && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center font-sans text-ink-muted">
                      No API request logs recorded for the current filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {reqLogs && (
            <div className="flex items-center justify-between text-xs text-ink-secondary">
              <span>
                Page {reqLogs.page} of {reqLogs.total_pages} ({reqLogs.total} logs)
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={reqPage <= 1}
                  onClick={() => setReqPage((p) => p - 1)}
                  className="rounded-lg border border-line bg-surface px-3 py-1 disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={reqPage >= reqLogs.total_pages}
                  onClick={() => setReqPage((p) => p + 1)}
                  className="rounded-lg border border-line bg-surface px-3 py-1 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'audit' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface p-3">
            <input
              type="text"
              placeholder="Search actor, action, or summary..."
              value={auditSearch}
              onChange={(e) => {
                setAuditSearch(e.target.value);
                setAuditPage(1);
              }}
              className="flex-1 min-w-[220px] rounded-lg border border-line bg-elevated px-3 py-1.5 text-xs text-ink"
            />
            <select
              value={auditStatus}
              onChange={(e) => {
                setAuditStatus(e.target.value);
                setAuditPage(1);
              }}
              className="rounded-lg border border-line bg-elevated px-3 py-1.5 text-xs text-ink"
            >
              <option value="">All Statuses</option>
              <option value="success">Success</option>
              <option value="denied">Denied</option>
              <option value="error">Error</option>
              <option value="pending_confirmation">Pending Confirm</option>
            </select>
          </div>

          <div className="overflow-x-auto rounded-xl border border-line bg-surface">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-line bg-elevated/60 text-[11px] uppercase text-ink-muted">
                <tr>
                  <th className="px-4 py-2.5">Timestamp</th>
                  <th className="px-4 py-2.5">Actor</th>
                  <th className="px-4 py-2.5">Action</th>
                  <th className="px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5">Summary</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {(auditLogs?.items || []).map((a) => (
                  <tr key={a.id} className="hover:bg-elevated/40">
                    <td className="px-4 py-2.5 text-[11px] text-ink-muted whitespace-nowrap">
                      {new Date(a.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5 font-medium text-ink">{a.actor_username}</td>
                    <td className="px-4 py-2.5 font-mono text-[11px] text-accent">{a.action}</td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
                          a.status === 'success'
                            ? 'bg-emerald-500/15 text-emerald-500'
                            : a.status === 'pending_confirmation'
                              ? 'bg-amber-500/15 text-amber-500'
                              : 'bg-rose-500/15 text-rose-500'
                        }`}
                      >
                        {a.status}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-ink-secondary">{a.summary}</td>
                  </tr>
                ))}
                {(!auditLogs || auditLogs.items.length === 0) && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-ink-muted">
                      No owner audit records yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {auditLogs && (
            <div className="flex items-center justify-between text-xs text-ink-secondary">
              <span>
                Page {auditLogs.page} of {auditLogs.total_pages} ({auditLogs.total} entries)
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={auditPage <= 1}
                  onClick={() => setAuditPage((p) => p - 1)}
                  className="rounded-lg border border-line bg-surface px-3 py-1 disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={auditPage >= auditLogs.total_pages}
                  onClick={() => setAuditPage((p) => p + 1)}
                  className="rounded-lg border border-line bg-surface px-3 py-1 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'errors' && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <section className="rounded-xl border border-line bg-surface p-4 space-y-3">
            <h3 className="text-sm font-semibold text-ink">Failed AI Requests</h3>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {(errLogs?.failed_ai_requests || []).length === 0 ? (
                <p className="py-6 text-center text-xs text-ink-muted">No failed AI requests logged.</p>
              ) : (
                errLogs!.failed_ai_requests.map((e, idx) => (
                  <div key={idx} className="rounded-lg border border-line bg-elevated/50 p-3 text-xs space-y-1">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="font-semibold text-rose-400">
                        {e.provider || 'ai'} / {e.model || 'unknown'}
                      </span>
                      <span className="text-ink-muted">{new Date(e.timestamp).toLocaleString()}</span>
                    </div>
                    <div className="font-mono text-[11px] text-ink-secondary">{e.message}</div>
                  </div>
                ))
              )}
            </div>
          </section>

          <section className="rounded-xl border border-line bg-surface p-4 space-y-3">
            <h3 className="text-sm font-semibold text-ink">Backend Process Error Ring Buffer</h3>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {(errLogs?.recent_app_errors || []).length === 0 ? (
                <p className="py-6 text-center text-xs text-ink-muted">No backend process exceptions captured.</p>
              ) : (
                errLogs!.recent_app_errors.map((e, idx) => (
                  <div key={idx} className="rounded-lg border border-line bg-elevated/50 p-3 text-xs space-y-1">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="font-semibold text-amber-400">
                        {e.source} • {e.category}
                      </span>
                      <span className="text-ink-muted">{new Date(e.timestamp).toLocaleString()}</span>
                    </div>
                    <div className="font-mono text-[11px] text-ink-secondary">{e.message}</div>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
};
