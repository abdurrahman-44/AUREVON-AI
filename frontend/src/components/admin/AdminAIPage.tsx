import React, { useEffect, useState } from 'react';
import { CheckCircle2, Cpu, KeyRound, Play, Sparkles, XCircle } from 'lucide-react';
import {
  configureCloudProvider,
  createSystemPromptVersion,
  runAdminAITest,
  updateAdminIntelligence,
} from '../../services/api';
import { AITestResponse, SystemAIConfigResponse } from '../../types';

interface AdminAIPageProps {
  intelligence: SystemAIConfigResponse | null;
  onUpdated: (next: SystemAIConfigResponse) => void;
  onNotice: (msg: string) => void;
  onError: (msg: string) => void;
}

export const AdminAIPage: React.FC<AdminAIPageProps> = ({
  intelligence,
  onUpdated,
  onNotice,
  onError,
}) => {
  const [cfgProvider, setCfgProvider] = useState('ollama');
  const [cfgModel, setCfgModel] = useState('qwen2.5:3b');
  const [cfgCtx, setCfgCtx] = useState(8192);
  const [cfgTemp, setCfgTemp] = useState(0.7);
  const [cfgAllowSwitch, setCfgAllowSwitch] = useState(false);
  const [cfgFallbackProv, setCfgFallbackProv] = useState('');
  const [cfgFallbackModel, setCfgFallbackModel] = useState('');
  const [cfgMemory, setCfgMemory] = useState(true);
  const [cfgRag, setCfgRag] = useState(true);
  const [cfgAgents, setCfgAgents] = useState(true);
  const [savingCfg, setSavingCfg] = useState(false);

  const [promptName, setPromptName] = useState('');
  const [promptNotes, setPromptNotes] = useState('');
  const [promptContent, setPromptContent] = useState('');
  const [savingPrompt, setSavingPrompt] = useState(false);

  const [keyProvider, setKeyProvider] = useState('openai');
  const [keySecret, setKeySecret] = useState('');
  const [savingKey, setSavingKey] = useState(false);

  const [testProvider, setTestProvider] = useState('');
  const [testModel, setTestModel] = useState('');
  const [testPrompt, setTestPrompt] = useState('Respond concisely with the word OK.');
  const [testingAI, setTestingAI] = useState(false);
  const [testResult, setTestResult] = useState<AITestResponse | null>(null);

  useEffect(() => {
    if (!intelligence) return;
    setCfgProvider(intelligence.active_provider);
    setCfgModel(intelligence.active_model);
    setCfgCtx(intelligence.context_window);
    setCfgTemp(intelligence.temperature);
    setCfgAllowSwitch(intelligence.allow_user_model_switching);
    setCfgFallbackProv(intelligence.fallback_provider || '');
    setCfgFallbackModel(intelligence.fallback_model || '');
    setCfgMemory(intelligence.enable_memory_injection);
    setCfgRag(intelligence.enable_rag_injection);
    setCfgAgents(intelligence.enable_agent_tools);
    if (intelligence.active_prompt && !promptContent) {
      setPromptContent(intelligence.active_prompt.content);
    }
    if (!testProvider) setTestProvider(intelligence.active_provider);
    if (!testModel) setTestModel(intelligence.active_model);
  }, [intelligence]);

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingCfg(true);
    try {
      const updated = await updateAdminIntelligence({
        active_provider: cfgProvider.trim(),
        active_model: cfgModel.trim(),
        context_window: cfgCtx,
        temperature: cfgTemp,
        allow_user_model_switching: cfgAllowSwitch,
        fallback_provider: cfgFallbackProv.trim() || null,
        fallback_model: cfgFallbackModel.trim() || null,
        enable_memory_injection: cfgMemory,
        enable_rag_injection: cfgRag,
        enable_agent_tools: cfgAgents,
      });
      onUpdated(updated);
      onNotice('Intelligence Core configuration saved.');
    } catch (err: any) {
      onError(err.message || 'Failed to save AI configuration');
    } finally {
      setSavingCfg(false);
    }
  };

  const handleRunTest = async (e: React.FormEvent) => {
    e.preventDefault();
    setTestingAI(true);
    setTestResult(null);
    try {
      const res = await runAdminAITest({
        provider: testProvider.trim() || undefined,
        model: testModel.trim() || undefined,
        prompt: testPrompt.trim() || undefined,
      });
      setTestResult(res);
    } catch (err: any) {
      onError(err.message || 'Live AI probe failed');
    } finally {
      setTestingAI(false);
    }
  };

  const handleCreatePrompt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!promptName.trim() || !promptContent.trim()) return;
    setSavingPrompt(true);
    try {
      const updated = await createSystemPromptVersion({
        name: promptName.trim(),
        content: promptContent.trim(),
        notes: promptNotes.trim() || undefined,
        activate: true,
      });
      onUpdated(updated);
      setPromptName('');
      setPromptNotes('');
      onNotice('Master prompt version published & activated.');
    } catch (err: any) {
      onError(err.message || 'Failed to publish prompt version');
    } finally {
      setSavingPrompt(false);
    }
  };

  const handleActivatePrompt = async (versionId: string) => {
    try {
      const updated = await updateAdminIntelligence({ active_prompt_version_id: versionId });
      onUpdated(updated);
      if (updated.active_prompt) setPromptContent(updated.active_prompt.content);
      onNotice('Activated selected system prompt version.');
    } catch (err: any) {
      onError(err.message || 'Failed to activate prompt version');
    }
  };

  const handleSaveKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keySecret.trim()) return;
    setSavingKey(true);
    try {
      await configureCloudProvider(keyProvider, keySecret.trim());
      setKeySecret('');
      onNotice(`Configured API credential for ${keyProvider}.`);
    } catch (err: any) {
      onError(err.message || 'Failed to configure provider key');
    } finally {
      setSavingKey(false);
    }
  };

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-line bg-surface p-5">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-accent" />
          <h2 className="text-sm font-semibold text-ink">Live AI Connectivity Test</h2>
        </div>
        <p className="mt-1 text-xs text-ink-muted">
          Send a bounded live test prompt directly to any configured provider &amp; model and measure latency.
        </p>

        <form onSubmit={handleRunTest} className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-4">
          <div>
            <label className="block text-[11px] font-medium text-ink-secondary">Provider</label>
            <select
              value={testProvider}
              onChange={(e) => setTestProvider(e.target.value)}
              className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
            >
              <option value="ollama">ollama (Local CPU)</option>
              <option value="openai">openai</option>
              <option value="groq">groq</option>
              <option value="deepseek">deepseek</option>
              <option value="production">production</option>
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-medium text-ink-secondary">Model Identifier</label>
            <input
              type="text"
              value={testModel}
              onChange={(e) => setTestModel(e.target.value)}
              placeholder="qwen2.5:3b"
              className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
            />
          </div>
          <div className="md:col-span-2 flex items-end gap-2">
            <div className="flex-1">
              <label className="block text-[11px] font-medium text-ink-secondary">Probe Prompt</label>
              <input
                type="text"
                value={testPrompt}
                onChange={(e) => setTestPrompt(e.target.value)}
                className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
              />
            </div>
            <button
              type="submit"
              disabled={testingAI}
              className="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50 transition"
            >
              <Play className="h-3.5 w-3.5" />
              {testingAI ? 'Testing...' : 'Run Probe'}
            </button>
          </div>
        </form>

        {testResult && (
          <div
            className={`mt-4 rounded-xl border p-4 text-xs ${
              testResult.success
                ? 'border-emerald-500/30 bg-emerald-500/5'
                : 'border-rose-500/30 bg-rose-500/5'
            }`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 font-semibold">
                {testResult.success ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                ) : (
                  <XCircle className="h-4 w-4 text-rose-500" />
                )}
                <span>
                  {testResult.provider} / {testResult.model} — {testResult.success ? 'PASSED' : 'FAILED'}
                </span>
              </div>
              <div className="text-ink-secondary">
                Latency: <strong className="text-ink">{testResult.latency_ms} ms</strong>
                {testResult.total_tokens !== null && testResult.total_tokens !== undefined && (
                  <span className="ml-3">Tokens: {testResult.total_tokens}</span>
                )}
              </div>
            </div>
            <div className="mt-2 rounded-lg bg-elevated/70 p-2.5 font-mono text-[11px] text-ink">
              {testResult.success
                ? testResult.response_preview || '[Empty response]'
                : testResult.error_message || 'Provider unreachable'}
            </div>
          </div>
        )}
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <form
          onSubmit={handleSaveConfig}
          className="rounded-xl border border-line bg-surface p-5 space-y-4 lg:col-span-8"
        >
          <div className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-accent" />
            <h2 className="text-sm font-semibold text-ink">Centralized Intelligence Core</h2>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-medium text-ink-secondary">Primary Provider</label>
              <select
                value={cfgProvider}
                onChange={(e) => setCfgProvider(e.target.value)}
                className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
              >
                <option value="ollama">ollama (Local Default)</option>
                <option value="openai">openai</option>
                <option value="groq">groq</option>
                <option value="deepseek">deepseek</option>
                <option value="production">production</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-ink-secondary">Pinned Default Model</label>
              <input
                type="text"
                value={cfgModel}
                onChange={(e) => setCfgModel(e.target.value)}
                className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-ink-secondary">Fallback Provider (Optional)</label>
              <input
                type="text"
                value={cfgFallbackProv}
                onChange={(e) => setCfgFallbackProv(e.target.value)}
                placeholder="e.g. groq"
                className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-ink-secondary">Fallback Model (Optional)</label>
              <input
                type="text"
                value={cfgFallbackModel}
                onChange={(e) => setCfgFallbackModel(e.target.value)}
                placeholder="e.g. llama-3.1-8b-instant"
                className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-ink-secondary">Context Window ({cfgCtx})</label>
              <input
                type="number"
                min={512}
                max={131072}
                value={cfgCtx}
                onChange={(e) => setCfgCtx(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-ink-secondary">Temperature ({cfgTemp})</label>
              <input
                type="number"
                step="0.05"
                min={0}
                max={2}
                value={cfgTemp}
                onChange={(e) => setCfgTemp(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 pt-2">
            {[
              { label: 'Allow Users to Switch Model', checked: cfgAllowSwitch, set: setCfgAllowSwitch },
              { label: 'Enable Long-Term Memory Injection', checked: cfgMemory, set: setCfgMemory },
              { label: 'Enable RAG Document Grounding', checked: cfgRag, set: setCfgRag },
              { label: 'Enable Autonomous Agent Tools', checked: cfgAgents, set: setCfgAgents },
            ].map((toggle) => (
              <label
                key={toggle.label}
                className="flex items-center justify-between rounded-lg border border-line bg-elevated/60 px-3 py-2 text-xs cursor-pointer"
              >
                <span className="text-ink font-medium">{toggle.label}</span>
                <input
                  type="checkbox"
                  checked={toggle.checked}
                  onChange={(e) => toggle.set(e.target.checked)}
                  className="h-4 w-4 accent-indigo-600"
                />
              </label>
            ))}
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={savingCfg}
              className="rounded-lg bg-accent px-4 py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50 transition"
            >
              {savingCfg ? 'Saving...' : 'Save Intelligence Configuration'}
            </button>
          </div>
        </form>

        <section className="rounded-xl border border-line bg-surface p-5 space-y-4 lg:col-span-4">
          <div className="flex items-center gap-2">
            <KeyRound className="h-4 w-4 text-accent" />
            <h2 className="text-sm font-semibold text-ink">Provider Key Status</h2>
          </div>

          <div className="space-y-1.5">
            {Object.entries(intelligence?.provider_keys_configured || {}).map(([prov, isSet]) => (
              <div
                key={prov}
                className="flex items-center justify-between rounded-lg border border-line bg-elevated/50 px-3 py-1.5 text-xs"
              >
                <span className="font-medium capitalize text-ink">{prov}</span>
                <span className={isSet ? 'text-emerald-500 font-semibold' : 'text-ink-muted'}>
                  {isSet ? 'Configured' : 'Not Set'}
                </span>
              </div>
            ))}
          </div>

          <form onSubmit={handleSaveKey} className="space-y-3 border-t border-line pt-4">
            <div>
              <label className="block text-xs font-medium text-ink-secondary">Provider</label>
              <select
                value={keyProvider}
                onChange={(e) => setKeyProvider(e.target.value)}
                className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
              >
                <option value="openai">OpenAI</option>
                <option value="groq">Groq</option>
                <option value="deepseek">DeepSeek</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-ink-secondary">Runtime API Key</label>
              <input
                type="password"
                value={keySecret}
                onChange={(e) => setKeySecret(e.target.value)}
                placeholder="Enter API key (never displayed after saving)"
                className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
              />
            </div>
            <button
              type="submit"
              disabled={savingKey || !keySecret.trim()}
              className="w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs font-semibold text-ink hover:border-accent/50 disabled:opacity-50 transition"
            >
              {savingKey ? 'Configuring...' : 'Configure Runtime Key'}
            </button>
          </form>
        </section>
      </div>

      <section className="rounded-xl border border-line bg-surface p-5 space-y-4">
        <div>
          <h2 className="text-sm font-semibold text-ink">Master System Prompts</h2>
          <p className="text-xs text-ink-muted">Version-controlled system instructions injected into chat sessions.</p>
        </div>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
          <form onSubmit={handleCreatePrompt} className="space-y-3 lg:col-span-7">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <input
                type="text"
                value={promptName}
                onChange={(e) => setPromptName(e.target.value)}
                placeholder="Version label (e.g. AUREVON Concise v2)"
                className="rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
                required
              />
              <input
                type="text"
                value={promptNotes}
                onChange={(e) => setPromptNotes(e.target.value)}
                placeholder="Change notes (optional)"
                className="rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
              />
            </div>
            <textarea
              rows={7}
              value={promptContent}
              onChange={(e) => setPromptContent(e.target.value)}
              className="w-full rounded-lg border border-line bg-elevated p-3 font-mono text-xs text-ink"
              required
            />
            <button
              type="submit"
              disabled={savingPrompt}
              className="rounded-lg bg-accent px-4 py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50 transition"
            >
              {savingPrompt ? 'Publishing...' : 'Publish & Activate Prompt Version'}
            </button>
          </form>

          <div className="space-y-2 lg:col-span-5 max-h-72 overflow-y-auto pr-1">
            {(intelligence?.prompt_versions || []).map((pv) => (
              <div
                key={pv.id}
                className={`rounded-lg border p-3 text-xs ${
                  pv.is_active ? 'border-accent/50 bg-accent/10' : 'border-line bg-elevated/40'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-ink">
                    v{pv.version_number} — {pv.name}
                  </span>
                  {pv.is_active ? (
                    <span className="rounded bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-500">
                      Active
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleActivatePrompt(pv.id)}
                      className="rounded border border-line px-2 py-0.5 text-[10px] font-medium text-ink hover:bg-elevated"
                    >
                      Activate
                    </button>
                  )}
                </div>
                {pv.notes && <p className="mt-1 text-[11px] text-ink-secondary">{pv.notes}</p>}
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
};
