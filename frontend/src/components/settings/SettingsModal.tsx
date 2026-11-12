import React, { useEffect, useState } from 'react';
import { Brain, Check, Lock, Monitor, Moon, Sun, X } from 'lucide-react';
import { updateUserSettings } from '../../services/api';
import { ModelInfo, UserSettings } from '../../types';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  settings: UserSettings | null;
  onUpdateSettings: (newSettings: UserSettings) => void;
  models: ModelInfo[];
  allowModelSwitching?: boolean;
  serverPinnedModel?: string;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  settings,
  onUpdateSettings,
  models,
  allowModelSwitching = false,
  serverPinnedModel = 'qwen2.5:3b',
}) => {
  const [theme, setTheme] = useState(settings?.theme || 'dark');
  const [defaultModel, setDefaultModel] = useState(settings?.default_model || serverPinnedModel);
  const [memoryEnabled, setMemoryEnabled] = useState(settings?.memory_enabled ?? true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (settings) {
      setTheme(settings.theme);
      setDefaultModel(settings.default_model);
      setMemoryEnabled(settings.memory_enabled);
    }
  }, [settings]);

  if (!isOpen) return null;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const updated = await updateUserSettings({
        theme,
        default_model: allowModelSwitching ? defaultModel : undefined,
        memory_enabled: memoryEnabled,
      });
      onUpdateSettings(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 1800);
    } catch (err: any) {
      setError(err.message || 'Could not save preferences');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg rounded-2xl border border-line bg-surface p-6 shadow-xl space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-ink">Preferences</h2>
            <p className="text-xs text-ink-secondary mt-0.5">Personal workspace theme and memory behavior</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-ink-muted hover:text-ink hover:bg-elevated">
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSave} className="space-y-5">
          {error && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/25 text-xs text-rose-500">
              {error}
            </div>
          )}

          {/* Theme */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-ink-secondary">Appearance</label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: 'dark', label: 'Dark', icon: <Moon size={14} /> },
                { id: 'light', label: 'Light', icon: <Sun size={14} /> },
                { id: 'system', label: 'System', icon: <Monitor size={14} /> },
              ].map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTheme(t.id)}
                  className={`flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl border text-xs font-medium transition-colors ${
                    theme === t.id
                      ? 'border-accent bg-accent/10 text-ink'
                      : 'border-line bg-canvas text-ink-secondary hover:text-ink'
                  }`}
                >
                  {t.icon}
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* Model Policy */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-ink-secondary">Active AI Model</label>
            {allowModelSwitching ? (
              <select
                value={defaultModel}
                onChange={(e) => setDefaultModel(e.target.value)}
                className="w-full px-3 py-2.5 rounded-xl border border-line bg-canvas text-xs font-mono text-ink"
              >
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.provider})
                  </option>
                ))}
              </select>
            ) : (
              <div className="flex items-center justify-between px-3.5 py-2.5 rounded-xl border border-line bg-canvas text-xs">
                <span className="font-mono text-ink">{serverPinnedModel}</span>
                <span className="inline-flex items-center gap-1 text-[11px] text-ink-muted">
                  <Lock size={11} />
                  Server-managed
                </span>
              </div>
            )}
          </div>

          {/* Memory Toggle */}
          <label className="flex items-center justify-between p-3.5 rounded-xl border border-line bg-canvas cursor-pointer">
            <div className="flex items-center gap-2.5">
              <Brain size={16} className="text-accent" />
              <div>
                <div className="text-xs font-medium text-ink">Persistent Long-Term Memory</div>
                <div className="text-[11px] text-ink-muted">Include saved memories as context in chats</div>
              </div>
            </div>
            <input
              type="checkbox"
              checked={memoryEnabled}
              onChange={(e) => setMemoryEnabled(e.target.checked)}
              className="rounded accent-accent"
            />
          </label>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-line">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl border border-line text-xs text-ink-secondary hover:text-ink"
            >
              Close
            </button>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-accent hover:bg-accent-hover text-white text-xs font-medium transition-colors"
            >
              {saved && <Check size={13} />}
              {saving ? 'Saving...' : saved ? 'Saved' : 'Save Preferences'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
