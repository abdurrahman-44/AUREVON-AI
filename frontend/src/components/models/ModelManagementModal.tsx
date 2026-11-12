import React, { useState } from 'react';
import { Cpu, Download, Key, Shield, X } from 'lucide-react';
import { configureCloudProvider } from '../../services/api';
import { ModelInfo, ProviderHealth } from '../../types';

interface ModelManagementModalProps {
  isOpen: boolean;
  onClose: () => void;
  models: ModelInfo[];
  providerHealths: ProviderHealth[];
  onRefresh: () => void;
  isOwner?: boolean;
}

export const ModelManagementModal: React.FC<ModelManagementModalProps> = ({
  isOpen,
  onClose,
  models,
  providerHealths,
  onRefresh,
  isOwner = false,
}) => {
  const [activeTab, setActiveTab] = useState<'catalog' | 'cloud' | 'pull'>('catalog');
  const [pullModelName, setPullModelName] = useState('qwen2.5:3b');
  const [pullStatus, setPullStatus] = useState<string | null>(null);
  const [pulling, setPulling] = useState(false);

  const [selectedCloudProvider, setSelectedCloudProvider] = useState('groq');
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [saveCloudStatus, setSaveCloudStatus] = useState<string | null>(null);
  const [savingKey, setSavingKey] = useState(false);

  if (!isOpen) return null;

  const handlePullModel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pullModelName.trim() || pulling) return;

    setPulling(true);
    setPullStatus(`Starting pull for ${pullModelName}...`);
    try {
      const token = localStorage.getItem('aurevon_token');
      const res = await fetch('/api/models/pull', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ name: pullModelName.trim() }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || 'Pull request rejected');
      }

      const reader = res.body?.getReader();
      const decoder = new TextDecoder('utf-8');
      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            try {
              const parsed = JSON.parse(line.slice(6));
              if (parsed.error) throw new Error(parsed.error);
              if (parsed.status) setPullStatus(parsed.status);
            } catch {
              // ignore non-json SSE line
            }
          }
        }
      }
      setPullStatus(`Model '${pullModelName}' is ready.`);
      onRefresh();
    } catch (err: any) {
      setPullStatus(`Error: ${err.message}`);
    } finally {
      setPulling(false);
    }
  };

  const handleSaveApiKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKeyInput.trim()) return;
    setSavingKey(true);
    setSaveCloudStatus(null);
    try {
      const res = await configureCloudProvider(selectedCloudProvider, apiKeyInput.trim());
      setSaveCloudStatus(`Configured ${res.provider} (${res.health?.status || 'checked'})`);
      setApiKeyInput('');
      onRefresh();
    } catch (err: any) {
      setSaveCloudStatus(`Error: ${err.message}`);
    } finally {
      setSavingKey(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl rounded-2xl border border-line bg-surface shadow-xl overflow-hidden flex flex-col max-h-[85vh]">
        <div className="px-6 py-4 border-b border-line flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Cpu size={17} className="text-accent" />
            <div>
              <h2 className="text-sm font-semibold text-ink">AI Models & Runtimes</h2>
              <p className="text-[11px] text-ink-secondary">Installed models and provider availability</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-ink-muted hover:text-ink hover:bg-elevated">
            <X size={16} />
          </button>
        </div>

        <div className="px-6 border-b border-line flex items-center gap-2 text-xs">
          <button
            onClick={() => setActiveTab('catalog')}
            className={`py-2.5 px-3 border-b-2 font-medium ${
              activeTab === 'catalog' ? 'border-accent text-ink' : 'border-transparent text-ink-muted'
            }`}
          >
            Available Models
          </button>
          {isOwner && (
            <>
              <button
                onClick={() => setActiveTab('cloud')}
                className={`py-2.5 px-3 border-b-2 font-medium ${
                  activeTab === 'cloud' ? 'border-accent text-ink' : 'border-transparent text-ink-muted'
                }`}
              >
                Cloud Keys (Owner)
              </button>
              <button
                onClick={() => setActiveTab('pull')}
                className={`py-2.5 px-3 border-b-2 font-medium ${
                  activeTab === 'pull' ? 'border-accent text-ink' : 'border-transparent text-ink-muted'
                }`}
              >
                Pull Ollama Model
              </button>
            </>
          )}
        </div>

        <div className="p-6 overflow-y-auto space-y-4">
          {activeTab === 'catalog' && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {providerHealths.map((ph) => (
                  <div key={ph.provider} className="rounded-xl border border-line bg-canvas p-2.5 text-xs">
                    <div className="font-semibold uppercase text-ink">{ph.provider}</div>
                    <div className={ph.status === 'healthy' ? 'text-emerald-500 text-[11px]' : 'text-ink-muted text-[11px]'}>
                      {ph.status}
                    </div>
                  </div>
                ))}
              </div>

              <div className="space-y-2">
                {models.map((m) => (
                  <div
                    key={m.id}
                    className="flex items-center justify-between rounded-xl border border-line bg-canvas px-4 py-3 text-xs"
                  >
                    <div>
                      <div className="font-mono font-medium text-ink">{m.id}</div>
                      <div className="text-[11px] text-ink-muted">
                        {m.provider} {m.size ? `• ${m.size}` : ''} • ctx {m.capabilities.context_length}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {m.capabilities.vision && (
                        <span className="px-2 py-0.5 rounded bg-elevated text-ink-secondary text-[10px]">Vision</span>
                      )}
                      {m.is_default && (
                        <span className="px-2 py-0.5 rounded bg-accent/15 text-accent text-[10px] font-medium">Default</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'cloud' && isOwner && (
            <form onSubmit={handleSaveApiKey} className="space-y-3 text-xs">
              <div className="flex items-center gap-2 text-ink-secondary">
                <Shield size={14} className="text-accent" />
                <span>Owner-only server provider configuration</span>
              </div>
              <select
                value={selectedCloudProvider}
                onChange={(e) => setSelectedCloudProvider(e.target.value)}
                className="w-full px-3 py-2.5 rounded-xl border border-line bg-canvas text-ink"
              >
                <option value="groq">Groq</option>
                <option value="openai">OpenAI</option>
                <option value="deepseek">DeepSeek</option>
              </select>
              <input
                type="password"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                placeholder="Enter provider API key..."
                className="w-full px-3 py-2.5 rounded-xl border border-line bg-canvas text-ink font-mono"
              />
              {saveCloudStatus && <p className="text-ink-secondary">{saveCloudStatus}</p>}
              <button
                type="submit"
                disabled={savingKey || !apiKeyInput.trim()}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-accent text-white font-medium disabled:opacity-50"
              >
                <Key size={13} />
                {savingKey ? 'Saving...' : 'Configure Key'}
              </button>
            </form>
          )}

          {activeTab === 'pull' && isOwner && (
            <form onSubmit={handlePullModel} className="space-y-3 text-xs">
              <p className="text-ink-secondary">Pull an open-weight model into the local Ollama runtime.</p>
              <input
                type="text"
                value={pullModelName}
                onChange={(e) => setPullModelName(e.target.value)}
                placeholder="e.g. qwen2.5:3b"
                className="w-full px-3 py-2.5 rounded-xl border border-line bg-canvas text-ink font-mono"
              />
              {pullStatus && <div className="p-3 rounded-xl border border-line bg-canvas font-mono">{pullStatus}</div>}
              <button
                type="submit"
                disabled={pulling}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-accent text-white font-medium disabled:opacity-50"
              >
                <Download size={13} />
                {pulling ? 'Pulling...' : 'Download Model'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
