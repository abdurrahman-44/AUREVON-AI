import React, { useEffect, useState } from 'react';
import { Copy, KeyRound, ShieldCheck } from 'lucide-react';
import {
  disableTwoFactor,
  enableTwoFactor,
  fetchSecurityEvents,
  fetchTwoFactorStatus,
  setupTwoFactor,
} from '../../services/api';
import { PaginatedSecurityEventsResponse, TwoFactorSetupResponse } from '../../types';

interface AdminSecurityPageProps {
  onNotice: (msg: string) => void;
  onError: (msg: string) => void;
}

export const AdminSecurityPage: React.FC<AdminSecurityPageProps> = ({ onNotice, onError }) => {
  const [totpEnabled, setTotpEnabled] = useState(false);
  const [setupData, setSetupData] = useState<TwoFactorSetupResponse | null>(null);
  const [verifyCode, setVerifyCode] = useState('');
  const [disableCode, setDisableCode] = useState('');
  const [busy2fa, setBusy2fa] = useState(false);

  const [events, setEvents] = useState<PaginatedSecurityEventsResponse | null>(null);
  const [evPage, setEvPage] = useState(1);
  const [severityFilter, setSeverityFilter] = useState('all');

  const load2FA = async () => {
    try {
      const st = await fetchTwoFactorStatus();
      setTotpEnabled(st.totp_enabled);
    } catch (err: any) {
      onError(err.message || 'Failed to load 2FA state');
    }
  };

  const loadEvents = async () => {
    try {
      const data = await fetchSecurityEvents({
        page: evPage,
        pageSize: 20,
        severity: severityFilter,
      });
      setEvents(data);
    } catch (err: any) {
      onError(err.message || 'Failed to load security telemetry');
    }
  };

  useEffect(() => {
    load2FA();
  }, []);

  useEffect(() => {
    loadEvents();
  }, [evPage, severityFilter]);

  const handleStartSetup = async () => {
    setBusy2fa(true);
    try {
      const res = await setupTwoFactor();
      setSetupData(res);
      setVerifyCode('');
    } catch (err: any) {
      onError(err.message || 'Failed to initiate 2FA setup');
    } finally {
      setBusy2fa(false);
    }
  };

  const handleEnable = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!verifyCode.trim()) return;
    setBusy2fa(true);
    try {
      const st = await enableTwoFactor(verifyCode.trim());
      setTotpEnabled(st.totp_enabled);
      setSetupData(null);
      setVerifyCode('');
      onNotice('Two-factor authentication (TOTP) is now enabled on your owner account.');
      loadEvents();
    } catch (err: any) {
      onError(err.message || 'Verification failed');
    } finally {
      setBusy2fa(false);
    }
  };

  const handleDisable = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!disableCode.trim()) return;
    setBusy2fa(true);
    try {
      const st = await disableTwoFactor(disableCode.trim());
      setTotpEnabled(st.totp_enabled);
      setDisableCode('');
      onNotice('Two-factor authentication disabled.');
      loadEvents();
    } catch (err: any) {
      onError(err.message || 'Failed to disable 2FA');
    } finally {
      setBusy2fa(false);
    }
  };

  const copyText = (txt: string, label: string) => {
    navigator.clipboard.writeText(txt).then(() => onNotice(`${label} copied to clipboard.`));
  };

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-line bg-surface p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="h-5 w-5 text-accent" />
            <div>
              <h2 className="text-sm font-semibold text-ink">Owner Two-Factor Authentication (TOTP)</h2>
              <p className="text-xs text-ink-muted">
                Optional RFC 6238 authenticator verification enforced on owner Control Centre sign-in.
              </p>
            </div>
          </div>
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold ${
              totpEnabled ? 'bg-emerald-500/15 text-emerald-500' : 'bg-elevated text-ink-secondary'
            }`}
          >
            {totpEnabled ? '2FA Enabled' : '2FA Disabled'}
          </span>
        </div>

        {!totpEnabled && !setupData && (
          <button
            type="button"
            onClick={handleStartSetup}
            disabled={busy2fa}
            className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50 transition"
          >
            <KeyRound className="h-3.5 w-3.5" />
            Configure Authenticator 2FA
          </button>
        )}

        {!totpEnabled && setupData && (
          <div className="rounded-xl border border-line bg-elevated/60 p-4 space-y-4 text-xs">
            <div>
              <p className="font-semibold text-ink">Step 1: Add Secret Key to Your Authenticator App</p>
              <p className="mt-0.5 text-ink-secondary">
                Enter this Base32 key manually into Google Authenticator, 1Password, Authy, or Ente Auth:
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <code className="rounded-lg border border-line bg-surface px-3 py-1.5 font-mono text-xs font-semibold text-accent">
                  {setupData.secret}
                </code>
                <button
                  type="button"
                  onClick={() => copyText(setupData.secret, 'Secret key')}
                  className="inline-flex items-center gap-1 rounded-lg border border-line px-2.5 py-1.5 text-[11px] hover:bg-surface"
                >
                  <Copy className="h-3 w-3" />
                  Copy Key
                </button>
                <button
                  type="button"
                  onClick={() => copyText(setupData.otpauth_uri, 'otpauth URI')}
                  className="inline-flex items-center gap-1 rounded-lg border border-line px-2.5 py-1.5 text-[11px] hover:bg-surface"
                >
                  <Copy className="h-3 w-3" />
                  Copy otpauth:// URI
                </button>
              </div>
            </div>

            <form onSubmit={handleEnable} className="flex flex-wrap items-end gap-3 border-t border-line pt-3">
              <div>
                <label className="block text-[11px] font-medium text-ink-secondary">
                  Step 2: Enter 6-digit code to activate
                </label>
                <input
                  type="text"
                  maxLength={8}
                  value={verifyCode}
                  onChange={(e) => setVerifyCode(e.target.value)}
                  placeholder="123456"
                  className="mt-1 w-40 rounded-lg border border-line bg-surface px-3 py-2 font-mono text-xs text-ink tracking-widest"
                  required
                />
              </div>
              <button
                type="submit"
                disabled={busy2fa}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                Verify &amp; Enable 2FA
              </button>
              <button
                type="button"
                onClick={() => setSetupData(null)}
                className="rounded-lg border border-line px-3 py-2 text-xs text-ink-secondary hover:bg-surface"
              >
                Cancel
              </button>
            </form>
          </div>
        )}

        {totpEnabled && (
          <form onSubmit={handleDisable} className="flex flex-wrap items-end gap-3 border-t border-line pt-4 text-xs">
            <div>
              <label className="block text-[11px] font-medium text-ink-secondary">
                Confirm current 6-digit code to disable 2FA
              </label>
              <input
                type="text"
                maxLength={8}
                value={disableCode}
                onChange={(e) => setDisableCode(e.target.value)}
                placeholder="123456"
                className="mt-1 w-40 rounded-lg border border-line bg-elevated px-3 py-2 font-mono text-xs text-ink tracking-widest"
                required
              />
            </div>
            <button
              type="submit"
              disabled={busy2fa}
              className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-2 text-xs font-semibold text-rose-500 hover:bg-rose-500/20 disabled:opacity-50"
            >
              Disable 2FA
            </button>
          </form>
        )}
      </section>

      <section className="rounded-xl border border-line bg-surface p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-ink">Authentication &amp; Access Security Events</h2>
            <p className="text-xs text-ink-muted">
              Tracks failed logins, owner sign-ins, denied unauthorized admin requests, and 2FA transitions.
            </p>
          </div>
          <select
            value={severityFilter}
            onChange={(e) => {
              setSeverityFilter(e.target.value);
              setEvPage(1);
            }}
            className="rounded-lg border border-line bg-elevated px-3 py-1.5 text-xs text-ink"
          >
            <option value="all">All Severities</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="critical">Critical</option>
          </select>
        </div>

        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-line bg-elevated/60 text-[11px] uppercase text-ink-muted">
              <tr>
                <th className="px-4 py-2.5">Timestamp</th>
                <th className="px-4 py-2.5">Severity</th>
                <th className="px-4 py-2.5">Event</th>
                <th className="px-4 py-2.5">Target / IP</th>
                <th className="px-4 py-2.5">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {(events?.items || []).map((ev) => (
                <tr key={ev.id} className="hover:bg-elevated/40">
                  <td className="px-4 py-2.5 text-[11px] text-ink-muted whitespace-nowrap">
                    {new Date(ev.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
                        ev.severity === 'critical'
                          ? 'bg-rose-500/15 text-rose-500'
                          : ev.severity === 'warning'
                            ? 'bg-amber-500/15 text-amber-500'
                            : 'bg-elevated text-ink-secondary'
                      }`}
                    >
                      {ev.severity}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 font-mono text-[11px] text-accent">{ev.event_type}</td>
                  <td className="px-4 py-2.5 text-[11px] text-ink-secondary">
                    <div>{ev.identifier || ev.path || 'system'}</div>
                    <div className="text-ink-muted">{ev.ip_address || 'local'}</div>
                  </td>
                  <td className="px-4 py-2.5 text-ink-secondary">{ev.detail}</td>
                </tr>
              ))}
              {(!events || events.items.length === 0) && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-ink-muted">
                    No security events recorded yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {events && (
          <div className="flex items-center justify-between text-xs text-ink-secondary">
            <span>
              Page {events.page} of {events.total_pages} ({events.total} events)
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={evPage <= 1}
                onClick={() => setEvPage((p) => p - 1)}
                className="rounded-lg border border-line bg-surface px-3 py-1 disabled:opacity-40"
              >
                Previous
              </button>
              <button
                type="button"
                disabled={evPage >= events.total_pages}
                onClick={() => setEvPage((p) => p + 1)}
                className="rounded-lg border border-line bg-surface px-3 py-1 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
};
