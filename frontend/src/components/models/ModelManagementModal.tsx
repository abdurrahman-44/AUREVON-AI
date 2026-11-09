import React, { useState } from 'react';
import { X, Cpu, Cloud, Download, Key, Check } from 'lucide-react';
import { ModelInfo, ProviderHealth } from '../../types';

interface ModelManagementModalProps {
  isOpen: boolean;
  onClose: () => void;
  models: ModelInfo[];
  providerHealths: ProviderHealth[];
  onRefresh: () => void;
}

export const ModelManagementModal: React.FC<ModelManagementModalProps> = ({
  isOpen,
  onClose,
  models,
  providerHealths,
  onRefresh,
}) => {
  const [activeTab, setActiveTab] = useState<'catalog' | 'cloud' | 'pull'>('catalog');
  const [pullModelName, setPullModelName] = useState('qwen2.5:3b');
  const [pullStatus, setPullStatus] = useState<string | null>(null);
  const [pulling, setPulling] = useState(false);

  // Cloud API keys state
  const [selectedCloudProvider, setSelectedCloudProvider] = useState('groq');
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [saveCloudStatus, setSaveCloudStatus] = useState<string | null>(null);
  const [savingKey, setSavingKey] = useState(false);

  if (!isOpen) return null;

  const handlePullModel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pullModelName.trim() || pulling) return;
    setPulling(true);
    setPullStatus('Initiating pull with Ollama runtime...');

    try {
      const res = await fetch('/api/models/pull', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: pullModelName.trim() }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setPullStatus(`Pull request sent for ${pullModelName}. Ollama is fetching layers.`);
      setTimeout(() => {
        onRefresh();
        setPulling(false);
      }, 3000);
    } catch (err: any) {
      setPullStatus(`Pull failed: ${err.message || 'Make sure Ollama is running.'}`);
      setPulling(false);
    }
  };

  const handleConfigureCloud = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKeyInput.trim() || savingKey) return;
    setSavingKey(true);
    setSaveCloudStatus(null);

    try {
      const res = await fetch('/api/models/configure', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: selectedCloudProvider,
          api_key: apiKeyInput.trim(),
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setSaveCloudStatus(`Successfully configured ${selectedCloudProvider.toUpperCase()}! Status: ${data.health.status}`);
      setApiKeyInput('');
      onRefresh();
    } catch (err: any) {
      setSaveCloudStatus(`Configuration failed: ${err.message}`);
    } finally {
      setSavingKey(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-2xl bg-charcoal-900 border border-charcoal-800 rounded-2xl shadow-2xl p-6 sm:p-8 max-h-[90vh] flex flex-col">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-charcoal-400 hover:text-white hover:bg-charcoal-800 transition-colors"
        >
          <X size={18} />
        </button>

        <h2 className="text-xl font-bold text-white tracking-tight mb-1">Model & Provider Management</h2>
        <p className="text-xs text-charcoal-400 mb-6">
          Inspect local open-weight models, pull weights from Ollama, or configure cloud API gateways.
        </p>

        {/* Tab Switcher */}
        <div className="flex items-center gap-2 border-b border-charcoal-800 pb-3 mb-6">
          <button
            onClick={() => setActiveTab('catalog')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
              activeTab === 'catalog'
                ? 'bg-brand-600 text-white shadow-sm'
                : 'text-charcoal-400 hover:text-charcoal-200 hover:bg-charcoal-800'
            }`}
          >
            <Cpu size={14} />
            <span>Active Catalog ({models.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('cloud')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
              activeTab === 'cloud'
                ? 'bg-brand-600 text-white shadow-sm'
                : 'text-charcoal-400 hover:text-charcoal-200 hover:bg-charcoal-800'
            }`}
          >
            <Cloud size={14} />
            <span>Cloud Adapters</span>
          </button>

          <button
            onClick={() => setActiveTab('pull')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
              activeTab === 'pull'
                ? 'bg-brand-600 text-white shadow-sm'
                : 'text-charcoal-400 hover:text-charcoal-200 hover:bg-charcoal-800'
            }`}
          >
            <Download size={14} />
            <span>Pull Local Weights</span>
          </button>
        </div>

        {/* Tab 1: Catalog */}
        {activeTab === 'catalog' && (
          <div className="flex-1 overflow-y-auto space-y-2 pr-1">
            {models.map((m) => (
              <div
                key={m.id}
                className="p-3.5 rounded-xl bg-charcoal-800/40 border border-charcoal-700/60 flex items-center justify-between"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-white">{m.name}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-charcoal-800 text-brand-300 border border-charcoal-700 font-mono">
                      {m.provider}
                    </span>
                    {m.is_default && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-medium">
                        Default
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-1.5 text-[11px] text-charcoal-400">
                    <span>Context: {m.capabilities?.context_length?.toLocaleString() || 8192} tokens</span>
                    {m.size && <span>Size: {m.size}</span>}
                    <span>Tools: {m.capabilities?.tools ? 'Supported' : 'No'}</span>
                    <span>Vision: {m.capabilities?.vision ? 'Supported' : 'No'}</span>
                  </div>
                </div>

                <div className="flex items-center gap-1 text-emerald-400 text-xs font-mono">
                  <Check size={14} />
                  <span>Available</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Tab 2: Cloud Adapters */}
        {activeTab === 'cloud' && (
          <div className="flex-1 overflow-y-auto space-y-6 pr-1">
            <div className="p-4 rounded-xl bg-charcoal-800/40 border border-charcoal-700/60">
              <h3 className="text-xs font-semibold text-white mb-2 flex items-center gap-1.5">
                <Key size={14} className="text-brand-400" />
                <span>Configure OpenAI-Compatible Gateway</span>
              </h3>
              <p className="text-xs text-charcoal-400 mb-4">
                Enter an API key for Groq, DeepSeek, or OpenAI. Keys are held in backend memory and never exposed to the public browser.
              </p>

              <form onSubmit={handleConfigureCloud} className="space-y-3">
                <div className="grid grid-cols-3 gap-2">
                  {['groq', 'openai', 'deepseek'].map((prov) => (
                    <button
                      key={prov}
                      type="button"
                      onClick={() => setSelectedCloudProvider(prov)}
                      className={`py-2 px-3 rounded-xl border text-xs font-semibold uppercase tracking-wider transition-all ${
                        selectedCloudProvider === prov
                          ? 'bg-charcoal-800 border-brand-500 text-white'
                          : 'bg-charcoal-800/40 border-charcoal-700/60 text-charcoal-400 hover:text-charcoal-200'
                      }`}
                    >
                      {prov}
                    </button>
                  ))}
                </div>

                <div>
                  <input
                    type="password"
                    value={apiKeyInput}
                    onChange={(e) => setApiKeyInput(e.target.value)}
                    placeholder={`Enter ${selectedCloudProvider.toUpperCase()} API Key (e.g. gsk_...)`}
                    className="w-full bg-charcoal-800 border border-charcoal-700 rounded-xl px-3 py-2 text-xs text-white placeholder-charcoal-500 focus:outline-none focus:border-brand-500 font-mono"
                  />
                </div>

                <button
                  type="submit"
                  disabled={savingKey || !apiKeyInput.trim()}
                  className="w-full py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold transition-all shadow-md shadow-brand-600/30 disabled:opacity-50"
                >
                  {savingKey ? 'Verifying Key...' : `Save & Activate ${selectedCloudProvider.toUpperCase()}`}
                </button>
              </form>

              {saveCloudStatus && (
                <div className="mt-3 p-2.5 rounded-lg bg-charcoal-800 border border-charcoal-700 text-xs text-charcoal-200">
                  {saveCloudStatus}
                </div>
              )}
            </div>

            {/* Provider Health Overview */}
            <div>
              <h4 className="text-xs font-semibold text-charcoal-300 uppercase tracking-wider mb-2">
                Active Provider Gateway Status
              </h4>
              <div className="grid grid-cols-2 gap-2">
                {providerHealths.map((ph) => (
                  <div key={ph.provider} className="p-3 rounded-xl bg-charcoal-800/30 border border-charcoal-700/50">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold uppercase text-white">{ph.provider}</span>
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                          ph.status === 'healthy'
                            ? 'bg-emerald-500/20 text-emerald-400'
                            : 'bg-amber-500/20 text-amber-400'
                        }`}
                      >
                        {ph.status}
                      </span>
                    </div>
                    <span className="text-[10px] text-charcoal-500 block truncate mt-1">{ph.url}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Pull Weights */}
        {activeTab === 'pull' && (
          <div className="flex-1 overflow-y-auto space-y-4 pr-1">
            <div className="p-4 rounded-xl bg-charcoal-800/40 border border-charcoal-700/60">
              <h3 className="text-xs font-semibold text-white mb-2 flex items-center gap-1.5">
                <Download size={14} className="text-brand-400" />
                <span>Pull Ollama Model Directly</span>
              </h3>
              <p className="text-xs text-charcoal-400 mb-4">
                Trigger downloading GGUF open-weight models into your local Ollama runtime. Recommended for 16GB RAM: `qwen2.5:3b`, `qwen3:4b`, or `llama3.2:3b`.
              </p>

              <form onSubmit={handlePullModel} className="space-y-3">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={pullModelName}
                    onChange={(e) => setPullModelName(e.target.value)}
                    placeholder="e.g. qwen2.5:3b or llama3.2:3b"
                    className="flex-1 bg-charcoal-800 border border-charcoal-700 rounded-xl px-3 py-2 text-xs text-white placeholder-charcoal-500 focus:outline-none focus:border-brand-500 font-mono"
                  />
                  <button
                    type="submit"
                    disabled={pulling || !pullModelName.trim()}
                    className="px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold transition-all disabled:opacity-50 flex items-center gap-1.5"
                  >
                    <Download size={13} />
                    <span>{pulling ? 'Pulling...' : 'Pull Model'}</span>
                  </button>
                </div>
              </form>

              {pullStatus && (
                <div className="mt-3 p-2.5 rounded-lg bg-charcoal-800 border border-charcoal-700 text-xs text-charcoal-200">
                  {pullStatus}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
