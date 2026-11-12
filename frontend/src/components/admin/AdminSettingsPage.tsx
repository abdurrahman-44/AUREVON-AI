import React, { useEffect, useState } from 'react';
import { AlertTriangle, Sliders } from 'lucide-react';
import { fetchPlatformSettings, updatePlatformSettings } from '../../services/api';
import { PlatformConfigResponse } from '../../types';

interface AdminSettingsPageProps {
  onNotice: (msg: string) => void;
  onError: (msg: string) => void;
}

export const AdminSettingsPage: React.FC<AdminSettingsPageProps> = ({ onNotice, onError }) => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [displayName, setDisplayName] = useState('AUREVON AI');
  const [maintenanceMode, setMaintenanceMode] = useState(false);
  const [maintenanceMessage, setMaintenanceMessage] = useState('');
  const [allowPublicReg, setAllowPublicReg] = useState(true);
  const [enableApiLogs, setEnableApiLogs] = useState(true);
  const [logRetentionDays, setLogRetentionDays] = useState(30);
  const [authLimit, setAuthLimit] = useState(15);
  const [chatLimit, setChatLimit] = useState(30);
  const [uploadLimit, setUploadLimit] = useState(20);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);

  const applyConfig = (cfg: PlatformConfigResponse) => {
    setDisplayName(cfg.app_display_name);
    setMaintenanceMode(cfg.maintenance_mode);
    setMaintenanceMessage(cfg.maintenance_message);
    setAllowPublicReg(cfg.allow_public_registration);
    setEnableApiLogs(cfg.enable_api_request_logging);
    setLogRetentionDays(cfg.log_retention_days);
    setAuthLimit(cfg.auth_rate_limit_per_min);
    setChatLimit(cfg.chat_rate_limit_per_min);
    setUploadLimit(cfg.upload_rate_limit_per_min);
    setUpdatedAt(cfg.updated_at);
  };

  useEffect(() => {
    setLoading(true);
    fetchPlatformSettings()
      .then(applyConfig)
      .catch((err) => onError(err.message || 'Failed to load platform settings'))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await updatePlatformSettings({
        app_display_name: displayName.trim(),
        maintenance_mode: maintenanceMode,
        maintenance_message: maintenanceMessage.trim(),
        allow_public_registration: allowPublicReg,
        enable_api_request_logging: enableApiLogs,
        log_retention_days: logRetentionDays,
        auth_rate_limit_per_min: authLimit,
        chat_rate_limit_per_min: chatLimit,
        upload_rate_limit_per_min: uploadLimit,
      });
      applyConfig(updated);
      onNotice('Platform settings saved and applied to live API runtime.');
    } catch (err: any) {
      onError(err.message || 'Failed to update platform settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-xl border border-line bg-surface p-8 text-center text-xs text-ink-muted">
        Loading platform governance settings...
      </div>
    );
  }

  return (
    <form onSubmit={handleSave} className="space-y-6">
      <section className="rounded-xl border border-line bg-surface p-5 space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Sliders className="h-4 w-4 text-accent" />
            <h2 className="text-sm font-semibold text-ink">Runtime Platform Governance</h2>
          </div>
          {updatedAt && (
            <span className="text-[11px] text-ink-muted">
              Last updated: {new Date(updatedAt).toLocaleString()}
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className="block text-xs font-medium text-ink-secondary">Platform Display Name</label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-secondary">Default Log Retention (Days)</label>
            <input
              type="number"
              min={1}
              max={365}
              value={logRetentionDays}
              onChange={(e) => setLogRetentionDays(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
              required
            />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <label className="flex items-center justify-between rounded-lg border border-line bg-elevated/60 px-3 py-2.5 text-xs cursor-pointer">
            <span className="font-medium text-ink">Allow Public Registration</span>
            <input
              type="checkbox"
              checked={allowPublicReg}
              onChange={(e) => setAllowPublicReg(e.target.checked)}
              className="h-4 w-4 accent-indigo-600"
            />
          </label>
          <label className="flex items-center justify-between rounded-lg border border-line bg-elevated/60 px-3 py-2.5 text-xs cursor-pointer">
            <span className="font-medium text-ink">Log HTTP API Telemetry</span>
            <input
              type="checkbox"
              checked={enableApiLogs}
              onChange={(e) => setEnableApiLogs(e.target.checked)}
              className="h-4 w-4 accent-indigo-600"
            />
          </label>
          <label
            className={`flex items-center justify-between rounded-lg border px-3 py-2.5 text-xs cursor-pointer ${
              maintenanceMode
                ? 'border-amber-500/50 bg-amber-500/10'
                : 'border-line bg-elevated/60'
            }`}
          >
            <span className="font-medium text-ink">Maintenance Mode</span>
            <input
              type="checkbox"
              checked={maintenanceMode}
              onChange={(e) => setMaintenanceMode(e.target.checked)}
              className="h-4 w-4 accent-amber-500"
            />
          </label>
        </div>

        {maintenanceMode && (
          <div className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2.5 text-xs text-amber-300">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
            <span>
              While Maintenance Mode is enabled, public user APIs (chat, conversations, registration, documents, agents) return HTTP 503. Control Centre (`/api/admin*`) and health routes remain accessible to the owner.
            </span>
          </div>
        )}

        <div>
          <label className="block text-xs font-medium text-ink-secondary">Maintenance Banner Message</label>
          <textarea
            rows={2}
            value={maintenanceMessage}
            onChange={(e) => setMaintenanceMessage(e.target.value)}
            className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
            required
          />
        </div>
      </section>

      <section className="rounded-xl border border-line bg-surface p-5 space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-ink">Sliding-Window Rate Limits (Requests / Minute)</h3>
          <p className="text-xs text-ink-muted">Changes take effect immediately in the active backend process.</p>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="block text-xs font-medium text-ink-secondary">Auth Routes (/min)</label>
            <input
              type="number"
              min={5}
              max={300}
              value={authLimit}
              onChange={(e) => setAuthLimit(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-secondary">Chat &amp; AI Routes (/min)</label>
            <input
              type="number"
              min={5}
              max={300}
              value={chatLimit}
              onChange={(e) => setChatLimit(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-secondary">Document Uploads (/min)</label>
            <input
              type="number"
              min={2}
              max={300}
              value={uploadLimit}
              onChange={(e) => setUploadLimit(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
            />
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-accent px-5 py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50 transition"
          >
            {saving ? 'Applying Settings...' : 'Save &amp; Apply Platform Settings'}
          </button>
        </div>
      </section>
    </form>
  );
};
