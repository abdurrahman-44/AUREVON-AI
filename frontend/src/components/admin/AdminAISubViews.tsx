import React, { useCallback, useEffect, useState } from 'react';
import {
  Activity,
  CheckCircle2,
  Cloud,
  Cpu,
  Database,
  RefreshCw,
  ShieldCheck,
  Trash2,
  Wrench,
} from 'lucide-react';
import {
  deleteAdminKnowledgeDoc,
  fetchAdminAIKnowledge,
  fetchAdminAIModels,
  fetchAdminAIPerformance,
  fetchAdminAIProviders,
  fetchAdminAITools,
  rebuildAdminKnowledgeIndex,
  selectAdminAIModel,
  updateAdminAITool,
  updateAdminIntelligence,
} from '../../services/api';
import { SystemAIConfigResponse } from '../../types';

interface SubViewProps {
  intelligence: SystemAIConfigResponse | null;
  onUpdated: (next: SystemAIConfigResponse) => void;
  onNotice: (msg: string) => void;
  onError: (msg: string) => void;
}

export const AdminAIModelsPanel: React.FC<SubViewProps> = ({
  intelligence,
  onUpdated,
  onNotice,
  onError,
}) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [maxOutput, setMaxOutput] = useState(2048);
  const [keepAlive, setKeepAlive] = useState(900);
  const [reqTimeout, setReqTimeout] = useState(120);
  const [streamingEnabled, setStreamingEnabled] = useState(true);

  const loadModels = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchAdminAIModels();
      setData(res);
      if (res.max_output_tokens) setMaxOutput(res.max_output_tokens);
      if (res.keep_alive_seconds !== undefined) setKeepAlive(res.keep_alive_seconds);
      if (res.request_timeout_seconds) setReqTimeout(res.request_timeout_seconds);
      if (res.streaming_enabled !== undefined) setStreamingEnabled(res.streaming_enabled);
    } catch (err: any) {
      onError(err.message || 'Failed to discover local models');
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    loadModels();
  }, [loadModels]);

  const handleSelectDefault = async (modelId: string) => {
    try {
      const next = await selectAdminAIModel({
        active_provider: 'ollama',
        active_model: modelId,
      });
      onUpdated(next);
      onNotice(`Default active model switched to ollama/${modelId}.`);
      loadModels();
    } catch (err: any) {
      onError(err.message || 'Failed to switch active model');
    }
  };

  const handleSetCoding = async (modelId: string) => {
    try {
      const next = await updateAdminIntelligence({
        coding_provider: 'ollama',
        coding_model: modelId || null,
      });
      onUpdated(next);
      onNotice(modelId ? `Coding specialist set to ollama/${modelId}.` : 'Coding specialist cleared.');
      loadModels();
    } catch (err: any) {
      onError(err.message || 'Failed to set coding specialist model');
    }
  };

  const handleSaveRuntimeParams = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const next = await updateAdminIntelligence({
        max_output_tokens: maxOutput,
        keep_alive_seconds: keepAlive,
        request_timeout_seconds: reqTimeout,
        streaming_enabled: streamingEnabled,
      });
      onUpdated(next);
      onNotice('Model runtime & keep-alive parameters updated.');
    } catch (err: any) {
      onError(err.message || 'Failed to update runtime parameters');
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
            <Cpu className="h-4 w-4 text-accent" />
            Local Ollama Discovery &amp; Loaded RAM State
          </h3>
          <p className="text-xs text-ink-muted">
            Discovered from <code className="font-mono">{data?.ollama_url || 'http://127.0.0.1:11434'}</code> —{' '}
            {data?.ollama_reachable ? 'Online' : 'Offline'}
          </p>
        </div>
        <button
          type="button"
          onClick={loadModels}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-elevated px-3 py-1.5 text-xs text-ink hover:bg-surface disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {(data?.installed_local_models || []).map((m: any) => (
          <div
            key={m.id}
            className={`rounded-xl border p-4 space-y-2.5 ${
              m.is_default ? 'border-accent/50 bg-accent/5' : 'border-line bg-surface'
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="font-mono text-xs font-semibold text-ink">{m.id}</div>
                <div className="text-[11px] text-ink-muted">
                  {m.parameter_size} · {m.quantization} · {m.size_gb} GB
                </div>
              </div>
              <span
                className={`px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase ${
                  m.status === 'loaded'
                    ? 'bg-emerald-500/15 text-emerald-500'
                    : 'bg-elevated text-ink-secondary'
                }`}
              >
                {m.status === 'loaded' ? 'Loaded in RAM' : 'Ready'}
              </span>
            </div>

            <div className="flex flex-wrap gap-1.5">
              {m.is_default ? (
                <span className="inline-flex items-center gap-1 rounded bg-accent/15 px-2 py-1 text-[10px] font-semibold text-accent">
                  <CheckCircle2 className="h-3 w-3" /> Default Active Model
                </span>
              ) : (
                <button
                  type="button"
                  onClick={() => handleSelectDefault(m.id)}
                  className="rounded border border-line bg-elevated px-2.5 py-1 text-[11px] text-ink hover:border-accent"
                >
                  Set as Default
                </button>
              )}

              {m.is_coding_default ? (
                <button
                  type="button"
                  onClick={() => handleSetCoding('')}
                  className="rounded bg-indigo-500/15 px-2.5 py-1 text-[10px] font-semibold text-indigo-400"
                >
                  Coding Specialist (Clear)
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => handleSetCoding(m.id)}
                  className="rounded border border-line bg-elevated px-2.5 py-1 text-[11px] text-ink-secondary hover:text-ink"
                >
                  Assign Coding Specialist
                </button>
              )}
            </div>
          </div>
        ))}

        {(!data?.installed_local_models || data.installed_local_models.length === 0) && (
          <div className="rounded-xl border border-line bg-surface p-4 text-xs text-ink-muted md:col-span-2">
            No local Ollama models discovered yet. Ensure Ollama is running (`ollama serve`) and refresh.
          </div>
        )}
      </div>

      <form onSubmit={handleSaveRuntimeParams} className="rounded-xl border border-line bg-surface p-4 space-y-3">
        <div className="text-xs font-semibold text-ink">Inference Runtime &amp; Keep-Alive Parameters</div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
          <div>
            <label className="block text-[11px] text-ink-secondary">Max Output Tokens</label>
            <input
              type="number"
              min={64}
              max={16384}
              value={maxOutput}
              onChange={(e) => setMaxOutput(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-1.5 text-xs text-ink"
            />
          </div>
          <div>
            <label className="block text-[11px] text-ink-secondary">Keep-Alive (seconds)</label>
            <input
              type="number"
              min={0}
              max={86400}
              value={keepAlive}
              onChange={(e) => setKeepAlive(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-1.5 text-xs text-ink"
            />
          </div>
          <div>
            <label className="block text-[11px] text-ink-secondary">Request Timeout (s)</label>
            <input
              type="number"
              min={10}
              max={600}
              value={reqTimeout}
              onChange={(e) => setReqTimeout(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-1.5 text-xs text-ink"
            />
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 rounded-lg border border-line bg-elevated/60 px-3 py-1.5 text-xs text-ink w-full cursor-pointer">
              <input
                type="checkbox"
                checked={streamingEnabled}
                onChange={(e) => setStreamingEnabled(e.target.checked)}
                className="accent-accent"
              />
              Streaming Enabled
            </label>
          </div>
        </div>
        <div className="flex items-center justify-between text-[11px] text-ink-muted">
          <span>Active Coding Model: {intelligence?.coding_model || 'Uses default active model'}</span>
          <button
            type="submit"
            className="rounded-lg bg-accent px-4 py-1.5 text-xs font-semibold text-white hover:bg-accent-hover"
          >
            Save Runtime Params
          </button>
        </div>
      </form>
    </div>
  );
};

export const AdminAIToolsPanel: React.FC<SubViewProps> = ({ onNotice, onError }) => {
  const [tools, setTools] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const loadTools = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchAdminAITools();
      setTools(res.tools || []);
    } catch (err: any) {
      onError(err.message || 'Failed to load AI tools');
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    loadTools();
  }, [loadTools]);

  const handlePatchTool = async (toolName: string, patch: Record<string, any>) => {
    try {
      await updateAdminAITool(toolName, patch);
      onNotice(`Updated policy for tool '${toolName}'.`);
      loadTools();
    } catch (err: any) {
      onError(err.message || `Failed to update tool '${toolName}'`);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
            <Wrench className="h-4 w-4 text-accent" />
            AI Tool Registry &amp; Governance
          </h3>
          <p className="text-xs text-ink-muted">Control permissions, execution timeouts, and monitor live tool call statistics.</p>
        </div>
        <button
          type="button"
          onClick={loadTools}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-elevated px-3 py-1.5 text-xs text-ink"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-line bg-surface">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-line bg-elevated/60 text-[11px] uppercase text-ink-muted">
            <tr>
              <th className="px-4 py-2.5">Tool</th>
              <th className="px-4 py-2.5">Enabled</th>
              <th className="px-4 py-2.5">Permission Tier</th>
              <th className="px-4 py-2.5">Timeout (s)</th>
              <th className="px-4 py-2.5">Calls (OK/Fail)</th>
              <th className="px-4 py-2.5">Avg Duration</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {tools.map((t) => (
              <tr key={t.tool_name} className="hover:bg-elevated/30">
                <td className="px-4 py-3">
                  <div className="font-mono font-semibold text-ink">{t.tool_name}</div>
                  <div className="text-[11px] text-ink-muted max-w-xs">{t.description}</div>
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => handlePatchTool(t.tool_name, { is_enabled: !t.is_enabled })}
                    className={`rounded-md px-2.5 py-1 text-[11px] font-semibold ${
                      t.is_enabled ? 'bg-emerald-500/15 text-emerald-500' : 'bg-rose-500/15 text-rose-500'
                    }`}
                  >
                    {t.is_enabled ? 'Enabled' : 'Disabled'}
                  </button>
                </td>
                <td className="px-4 py-3">
                  <select
                    value={t.permission_level}
                    onChange={(e) => handlePatchTool(t.tool_name, { permission_level: e.target.value })}
                    className="rounded border border-line bg-elevated px-2 py-1 text-xs text-ink"
                  >
                    <option value="standard">standard</option>
                    <option value="owner_only">owner_only</option>
                    <option value="disabled">disabled</option>
                  </select>
                </td>
                <td className="px-4 py-3">
                  <input
                    type="number"
                    min={1}
                    max={30}
                    defaultValue={t.timeout_seconds}
                    onBlur={(e) => {
                      const v = Number(e.target.value);
                      if (v >= 1 && v <= 30 && v !== t.timeout_seconds) {
                        handlePatchTool(t.tool_name, { timeout_seconds: v });
                      }
                    }}
                    className="w-16 rounded border border-line bg-elevated px-2 py-1 text-xs text-ink"
                  />
                </td>
                <td className="px-4 py-3 font-mono">
                  {t.total_calls} ({t.successful_calls}/{t.failed_calls})
                </td>
                <td className="px-4 py-3 font-mono">{t.avg_duration_ms} ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export const AdminAIPerformancePanel: React.FC<SubViewProps> = ({ onError }) => {
  const [range, setRange] = useState<'24h' | '7d' | '30d'>('7d');
  const [perf, setPerf] = useState<any>(null);

  const loadPerf = useCallback(async () => {
    try {
      const res = await fetchAdminAIPerformance(range);
      setPerf(res);
    } catch (err: any) {
      onError(err.message || 'Failed to load AI performance metrics');
    }
  }, [range, onError]);

  useEffect(() => {
    loadPerf();
  }, [loadPerf]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
          <Activity className="h-4 w-4 text-accent" />
          Inference Latency &amp; Intent Routing Breakdown
        </h3>
        <div className="flex items-center gap-1 rounded-lg border border-line bg-surface p-1 text-xs">
          {(['24h', '7d', '30d'] as const).map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => setRange(r)}
              className={`rounded px-2.5 py-1 ${range === r ? 'bg-accent text-white font-semibold' : 'text-ink-muted hover:text-ink'}`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <div className="rounded-xl border border-line bg-surface p-3.5">
          <div className="text-[10px] uppercase text-ink-muted">Requests ({range})</div>
          <div className="mt-1 text-xl font-semibold text-ink">{perf?.total_requests ?? 0}</div>
        </div>
        <div className="rounded-xl border border-line bg-surface p-3.5">
          <div className="text-[10px] uppercase text-ink-muted">Success Rate</div>
          <div className="mt-1 text-xl font-semibold text-emerald-500">
            {perf?.success_rate_pct != null ? `${perf.success_rate_pct}%` : '—'}
          </div>
        </div>
        <div className="rounded-xl border border-line bg-surface p-3.5">
          <div className="text-[10px] uppercase text-ink-muted">Median Latency</div>
          <div className="mt-1 text-xl font-semibold text-ink">
            {perf?.median_latency_ms != null ? `${perf.median_latency_ms} ms` : '—'}
          </div>
        </div>
        <div className="rounded-xl border border-line bg-surface p-3.5">
          <div className="text-[10px] uppercase text-ink-muted">P95 Latency</div>
          <div className="mt-1 text-xl font-semibold text-amber-500">
            {perf?.p95_latency_ms != null ? `${perf.p95_latency_ms} ms` : '—'}
          </div>
        </div>
        <div className="rounded-xl border border-line bg-surface p-3.5">
          <div className="text-[10px] uppercase text-ink-muted">Avg TTFT</div>
          <div className="mt-1 text-xl font-semibold text-ink">
            {perf?.avg_ttft_ms != null ? `${perf.avg_ttft_ms} ms` : '—'}
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-line bg-surface p-4 space-y-2">
        <div className="text-xs font-semibold text-ink">Intent Distribution</div>
        <div className="space-y-1.5">
          {(perf?.intent_breakdown || []).map((item: any) => (
            <div key={item.intent} className="flex items-center justify-between text-xs">
              <span className="font-mono text-ink-secondary">{item.intent}</span>
              <span className="font-mono font-semibold text-ink">{item.count}</span>
            </div>
          ))}
          {(!perf?.intent_breakdown || perf.intent_breakdown.length === 0) && (
            <div className="text-xs text-ink-muted">No AI telemetry recorded in this window yet.</div>
          )}
        </div>
      </div>
    </div>
  );
};

export const AdminAIKnowledgePanel: React.FC<SubViewProps> = ({ onNotice, onError }) => {
  const [knowledge, setKnowledge] = useState<any>(null);
  const [rebuilding, setRebuilding] = useState(false);

  const loadKnowledge = useCallback(async () => {
    try {
      const res = await fetchAdminAIKnowledge();
      setKnowledge(res);
    } catch (err: any) {
      onError(err.message || 'Failed to load knowledge index');
    }
  }, [onError]);

  useEffect(() => {
    loadKnowledge();
  }, [loadKnowledge]);

  const handleRebuild = async () => {
    setRebuilding(true);
    try {
      const res = await rebuildAdminKnowledgeIndex();
      onNotice(`FTS5 index rebuilt (${res.indexed_chunks} chunks indexed).`);
      loadKnowledge();
    } catch (err: any) {
      onError(err.message || 'Failed to rebuild FTS5 index');
    } finally {
      setRebuilding(false);
    }
  };

  const handleDeleteDoc = async (id: string, filename: string) => {
    try {
      await deleteAdminKnowledgeDoc(id);
      onNotice(`Removed indexed document '${filename}'.`);
      loadKnowledge();
    } catch (err: any) {
      onError(err.message || 'Failed to delete document');
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
            <Database className="h-4 w-4 text-accent" />
            Knowledge Base &amp; SQLite FTS5 Search Index
          </h3>
          <p className="text-xs text-ink-muted">
            {knowledge?.total_documents ?? 0} documents · {knowledge?.total_chunks ?? 0} chunks · FTS5:{' '}
            {knowledge?.fts_available ? `Active (${knowledge?.fts_indexed_chunks} indexed)` : 'Fallback'}
          </p>
        </div>
        <button
          type="button"
          onClick={handleRebuild}
          disabled={rebuilding}
          className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${rebuilding ? 'animate-spin' : ''}`} />
          {rebuilding ? 'Rebuilding...' : 'Rebuild FTS5 Index'}
        </button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-line bg-surface">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-line bg-elevated/60 text-[11px] uppercase text-ink-muted">
            <tr>
              <th className="px-4 py-2.5">Filename</th>
              <th className="px-4 py-2.5">Type</th>
              <th className="px-4 py-2.5">Chunks</th>
              <th className="px-4 py-2.5">Status</th>
              <th className="px-4 py-2.5">SHA-256 Prefix</th>
              <th className="px-4 py-2.5 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {(knowledge?.documents || []).map((d: any) => (
              <tr key={d.id} className="hover:bg-elevated/30">
                <td className="px-4 py-2.5 font-medium text-ink">{d.filename}</td>
                <td className="px-4 py-2.5 font-mono uppercase">{d.file_type}</td>
                <td className="px-4 py-2.5 font-mono">{d.chunk_count}</td>
                <td className="px-4 py-2.5">{d.processing_status}</td>
                <td className="px-4 py-2.5 font-mono text-ink-muted">
                  {d.content_hash ? d.content_hash.slice(0, 12) : '—'}
                </td>
                <td className="px-4 py-2.5 text-right">
                  <button
                    type="button"
                    onClick={() => handleDeleteDoc(d.id, d.filename)}
                    className="inline-flex items-center gap-1 rounded px-2 py-1 text-rose-500 hover:bg-rose-500/10"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Remove
                  </button>
                </td>
              </tr>
            ))}
            {(!knowledge?.documents || knowledge.documents.length === 0) && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-ink-muted">
                  No documents indexed yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export const AdminAIProvidersPanel: React.FC<SubViewProps> = ({
  intelligence,
  onUpdated,
  onNotice,
  onError,
}) => {
  const [providersData, setProvidersData] = useState<any>(null);
  const [cloudEnabled, setCloudEnabled] = useState(Boolean(intelligence?.cloud_inference_enabled));
  const [requireConsent, setRequireConsent] = useState(intelligence?.require_cloud_consent ?? true);
  const [dailyLimit, setDailyLimit] = useState(intelligence?.cloud_daily_limit ?? 100);
  const [webSearchGlobal, setWebSearchGlobal] = useState(Boolean(intelligence?.web_search_enabled));

  const loadProviders = useCallback(async () => {
    try {
      const res = await fetchAdminAIProviders();
      setProvidersData(res);
      setCloudEnabled(Boolean(res.cloud_inference_enabled));
      setRequireConsent(Boolean(res.require_cloud_consent));
      setDailyLimit(Number(res.cloud_daily_limit || 100));
    } catch (err: any) {
      onError(err.message || 'Failed to load provider governance');
    }
  }, [onError]);

  useEffect(() => {
    loadProviders();
  }, [loadProviders]);

  const handleSavePolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const next = await updateAdminIntelligence({
        cloud_inference_enabled: cloudEnabled,
        require_cloud_consent: requireConsent,
        cloud_daily_limit: dailyLimit,
        web_search_enabled: webSearchGlobal,
      });
      onUpdated(next);
      onNotice('Cloud & Web Search governance policy saved.');
      loadProviders();
    } catch (err: any) {
      onError(err.message || 'Failed to save provider policy');
    }
  };

  return (
    <div className="space-y-5">
      <form onSubmit={handleSavePolicy} className="rounded-xl border border-line bg-surface p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Cloud className="h-4 w-4 text-accent" />
          <h3 className="text-sm font-semibold text-ink">Optional Cloud &amp; External Search Policy</h3>
        </div>
        <p className="text-xs text-ink-muted">
          Local-first by default. Cloud providers are disabled unless explicitly enabled here and consented to per request.
        </p>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="flex items-center gap-2 rounded-lg border border-line bg-elevated/60 px-3 py-2 text-xs text-ink cursor-pointer">
            <input
              type="checkbox"
              checked={cloudEnabled}
              onChange={(e) => setCloudEnabled(e.target.checked)}
              className="accent-accent"
            />
            Allow Cloud Providers
          </label>
          <label className="flex items-center gap-2 rounded-lg border border-line bg-elevated/60 px-3 py-2 text-xs text-ink cursor-pointer">
            <input
              type="checkbox"
              checked={requireConsent}
              onChange={(e) => setRequireConsent(e.target.checked)}
              className="accent-accent"
            />
            Require User Consent
          </label>
          <label className="flex items-center gap-2 rounded-lg border border-line bg-elevated/60 px-3 py-2 text-xs text-ink cursor-pointer">
            <input
              type="checkbox"
              checked={webSearchGlobal}
              onChange={(e) => setWebSearchGlobal(e.target.checked)}
              className="accent-accent"
            />
            Allow Live Web Search
          </label>
          <div>
            <input
              type="number"
              min={1}
              max={100000}
              value={dailyLimit}
              onChange={(e) => setDailyLimit(Number(e.target.value))}
              className="w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
              title="Daily cloud request cap"
            />
          </div>
        </div>

        <button
          type="submit"
          className="rounded-lg bg-accent px-4 py-2 text-xs font-semibold text-white hover:bg-accent-hover"
        >
          Save Governance Policy
        </button>
      </form>

      <div className="rounded-xl border border-line bg-surface p-4 space-y-3">
        <div className="text-xs font-semibold text-ink flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-accent" />
          Provider Usage &amp; Estimated Cost Telemetry
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-line text-[11px] uppercase text-ink-muted">
              <tr>
                <th className="py-2 pr-4">Provider</th>
                <th className="py-2 pr-4">Scope</th>
                <th className="py-2 pr-4">Requests</th>
                <th className="py-2 pr-4">Total Tokens</th>
                <th className="py-2">Est. Cost (USD)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {(providersData?.usage || []).map((u: any) => (
                <tr key={u.provider}>
                  <td className="py-2 pr-4 font-mono font-semibold text-ink">{u.provider}</td>
                  <td className="py-2 pr-4">{u.is_cloud ? 'Cloud' : 'Local'}</td>
                  <td className="py-2 pr-4 font-mono">{u.requests}</td>
                  <td className="py-2 pr-4 font-mono">{u.total_tokens}</td>
                  <td className="py-2 font-mono">${Number(u.estimated_cost_usd || 0).toFixed(4)}</td>
                </tr>
              ))}
              {(!providersData?.usage || providersData.usage.length === 0) && (
                <tr>
                  <td colSpan={5} className="py-4 text-center text-ink-muted">
                    No provider usage logged yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
