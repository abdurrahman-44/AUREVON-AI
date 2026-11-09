import React, { useState, useEffect } from 'react';
import { X, Moon, Sun, Monitor, Brain, Check, Shield } from 'lucide-react';
import { UserSettings, ModelInfo } from '../../types';
import { updateUserSettings } from '../../services/api';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  settings: UserSettings | null;
  onUpdateSettings: (newSettings: UserSettings) => void;
  models: ModelInfo[];
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  settings,
  onUpdateSettings,
  models,
}) => {
  const [theme, setTheme] = useState(settings?.theme || 'dark');
  const [defaultModel, setDefaultModel] = useState(settings?.default_model || 'qwen2.5:3b');
  const [memoryEnabled, setMemoryEnabled] = useState(settings?.memory_enabled ?? true);
  const [systemPrompt, setSystemPrompt] = useState(
    settings?.other_preferences?.system_prompt ||
      'You are AUREVON AI, an intelligent, helpful, and precise assistant.'
  );
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    if (settings) {
      setTheme(settings.theme);
      setDefaultModel(settings.default_model);
      setMemoryEnabled(settings.memory_enabled);
      setSystemPrompt(
        settings.other_preferences?.system_prompt ||
          'You are AUREVON AI, an intelligent, helpful, and precise assistant.'
      );
    }
  }, [settings]);

  if (!isOpen) return null;

  const handleSave = async () => {
    setSaving(true);
    setSavedSuccess(false);
    try {
      const updated = await updateUserSettings({
        theme,
        default_model: defaultModel,
        memory_enabled: memoryEnabled,
        other_preferences: {
          system_prompt: systemPrompt,
        },
      });
      onUpdateSettings(updated);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 2000);
    } catch (err) {
      console.error('Failed to update settings:', err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-lg bg-charcoal-900 border border-charcoal-800 rounded-2xl shadow-2xl p-6 sm:p-8 max-h-[90vh] overflow-y-auto">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-charcoal-400 hover:text-white hover:bg-charcoal-800 transition-colors"
        >
          <X size={18} />
        </button>

        <h2 className="text-xl font-bold text-white tracking-tight mb-1">Preferences & Settings</h2>
        <p className="text-xs text-charcoal-400 mb-6">Customize inference parameters, themes, and memory retention.</p>

        <div className="space-y-6">
          {/* Theme Mode */}
          <div>
            <label className="block text-xs font-semibold text-charcoal-300 uppercase tracking-wider mb-2">
              Appearance
            </label>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => setTheme('dark')}
                className={`flex items-center justify-center gap-2 py-2 px-3 rounded-xl border text-xs font-medium transition-all ${
                  theme === 'dark'
                    ? 'bg-charcoal-800 border-brand-500 text-white shadow-sm'
                    : 'bg-charcoal-800/40 border-charcoal-700/60 text-charcoal-400 hover:text-charcoal-200'
                }`}
              >
                <Moon size={14} className={theme === 'dark' ? 'text-brand-400' : ''} />
                <span>Dark</span>
              </button>
              <button
                type="button"
                onClick={() => setTheme('light')}
                className={`flex items-center justify-center gap-2 py-2 px-3 rounded-xl border text-xs font-medium transition-all ${
                  theme === 'light'
                    ? 'bg-charcoal-800 border-brand-500 text-white shadow-sm'
                    : 'bg-charcoal-800/40 border-charcoal-700/60 text-charcoal-400 hover:text-charcoal-200'
                }`}
              >
                <Sun size={14} className={theme === 'light' ? 'text-amber-400' : ''} />
                <span>Light</span>
              </button>
              <button
                type="button"
                onClick={() => setTheme('system')}
                className={`flex items-center justify-center gap-2 py-2 px-3 rounded-xl border text-xs font-medium transition-all ${
                  theme === 'system'
                    ? 'bg-charcoal-800 border-brand-500 text-white shadow-sm'
                    : 'bg-charcoal-800/40 border-charcoal-700/60 text-charcoal-400 hover:text-charcoal-200'
                }`}
              >
                <Monitor size={14} className={theme === 'system' ? 'text-sky-400' : ''} />
                <span>System</span>
              </button>
            </div>
          </div>

          {/* Default Model */}
          <div>
            <label className="block text-xs font-semibold text-charcoal-300 uppercase tracking-wider mb-2">
              Default Inference Model
            </label>
            <div className="relative">
              <select
                value={defaultModel}
                onChange={(e) => setDefaultModel(e.target.value)}
                className="w-full bg-charcoal-800 border border-charcoal-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-500"
              >
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.provider})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Long Term Memory Toggle */}
          <div className="flex items-center justify-between p-3.5 rounded-xl bg-charcoal-800/40 border border-charcoal-700/60">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-charcoal-800 text-brand-400 mt-0.5">
                <Brain size={16} />
              </div>
              <div>
                <span className="block text-xs font-semibold text-white">Cross-Conversation Memory</span>
                <span className="block text-[11px] text-charcoal-400 mt-0.5">
                  Allows AUREVON to recall important user facts, projects, and style guidelines across chats.
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setMemoryEnabled(!memoryEnabled)}
              className={`w-11 h-6 rounded-full transition-colors relative flex-shrink-0 ${
                memoryEnabled ? 'bg-brand-600' : 'bg-charcoal-700'
              }`}
            >
              <div
                className={`w-4 h-4 rounded-full bg-white transition-transform absolute top-1 left-1 ${
                  memoryEnabled ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>

          {/* System Instructions / Prompt */}
          <div>
            <label className="block text-xs font-semibold text-charcoal-300 uppercase tracking-wider mb-2">
              Custom Persona / Instructions
            </label>
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={3}
              className="w-full bg-charcoal-800 border border-charcoal-700 rounded-xl p-3 text-xs text-white placeholder-charcoal-500 focus:outline-none focus:border-brand-500 resize-none font-mono"
            />
          </div>
        </div>

        {/* Footer Actions */}
        <div className="mt-8 pt-4 border-t border-charcoal-800 flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-[11px] text-emerald-400">
            <Shield size={13} />
            <span>Settings stored securely on local database</span>
          </div>

          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold tracking-wide transition-all shadow-md shadow-brand-600/30 disabled:opacity-50"
          >
            {savedSuccess ? <Check size={14} /> : null}
            <span>{savedSuccess ? 'Saved!' : saving ? 'Saving...' : 'Save Changes'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
