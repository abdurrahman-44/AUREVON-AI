import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, ArrowLeft, CheckCircle2, KeyRound, Lock, Moon, Shield, Sun, X } from 'lucide-react';
import {
  TwoFactorRequiredError,
  adminLogin,
  bootstrapOwner,
  fetchAdminAnalytics,
  fetchAdminIntelligence,
  fetchAdminMonitoring,
  fetchAdminUsers,
  fetchBootstrapStatus,
} from '../../services/api';
import {
  AdminAnalyticsResponse,
  AdminSectionRoute,
  BootstrapStatus,
  PaginatedUsersResponse,
  SystemAIConfigResponse,
  SystemMonitoringResponse,
  User,
} from '../../types';
import { AdminAIPage } from './AdminAIPage';
import { AdminDashboardPage } from './AdminDashboardPage';
import { AdminLayout } from './AdminLayout';
import { AdminLogsPage } from './AdminLogsPage';
import { AdminSecurityPage } from './AdminSecurityPage';
import { AdminSettingsPage } from './AdminSettingsPage';
import { AdminSystemPage } from './AdminSystemPage';
import { AdminTerminalPage } from './AdminTerminalPage';
import { AdminUsersPage } from './AdminUsersPage';

interface AdminConsoleProps {
  currentUser: User | null;
  routePath: string;
  onNavigate: (path: string) => void;
  onAuthSuccess: (user: User, token: string) => void;
  onExitAdmin: () => void;
  onLogout: () => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
}

const VALID_ADMIN_ROUTES: AdminSectionRoute[] = [
  '/admin',
  '/admin/terminal',
  '/admin/ai',
  '/admin/users',
  '/admin/system',
  '/admin/logs',
  '/admin/security',
  '/admin/settings',
];

function normalizeAdminRoute(path: string): AdminSectionRoute {
  const clean = path.replace(/\/+$/, '') || '/admin';
  return (VALID_ADMIN_ROUTES.includes(clean as AdminSectionRoute)
    ? clean
    : '/admin') as AdminSectionRoute;
}

export const AdminConsole: React.FC<AdminConsoleProps> = ({
  currentUser,
  routePath,
  onNavigate,
  onAuthSuccess,
  onExitAdmin,
  onLogout,
  theme,
  onToggleTheme,
}) => {
  const activeRoute = normalizeAdminRoute(routePath);

  const [bootstrapStatus, setBootstrapStatus] = useState<BootstrapStatus | null>(null);
  const [loginIdentifier, setLoginIdentifier] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [totpRequired, setTotpRequired] = useState(false);
  const [loginTotp, setLoginTotp] = useState('');
  const [bootUsername, setBootUsername] = useState('');
  const [bootEmail, setBootEmail] = useState('');
  const [bootPassword, setBootPassword] = useState('');
  const [bootToken, setBootToken] = useState('');
  const [authError, setAuthError] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(false);

  const [range, setRange] = useState<'24h' | '7d' | '30d' | '90d' | 'custom'>('7d');
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');

  const [analytics, setAnalytics] = useState<AdminAnalyticsResponse | null>(null);
  const [usersData, setUsersData] = useState<PaginatedUsersResponse | null>(null);
  const [monitoring, setMonitoring] = useState<SystemMonitoringResponse | null>(null);
  const [intelligence, setIntelligence] = useState<SystemAIConfigResponse | null>(null);

  const [userPage, setUserPage] = useState(1);
  const [userSearch, setUserSearch] = useState('');
  const [userRoleFilter, setUserRoleFilter] = useState('all');
  const [userStatusFilter, setUserStatusFilter] = useState('all');

  const [autoRefreshSeconds, setAutoRefreshSeconds] = useState(30);
  const [refreshing, setRefreshing] = useState(false);
  const [consoleError, setConsoleError] = useState<string | null>(null);
  const [statusNotice, setStatusNotice] = useState<string | null>(null);

  const isOwner = currentUser?.role === 'owner';

  useEffect(() => {
    fetchBootstrapStatus()
      .then(setBootstrapStatus)
      .catch(() => {
        /* ignore offline status probe */
      });
  }, []);

  const refreshUsers = useCallback(async () => {
    if (!isOwner) return;
    try {
      const usr = await fetchAdminUsers({
        page: userPage,
        pageSize: 15,
        search: userSearch,
        role: userRoleFilter,
        isActive: userStatusFilter,
      });
      setUsersData(usr);
    } catch (err: any) {
      setConsoleError(err.message || 'Failed to load user list');
    }
  }, [isOwner, userPage, userSearch, userRoleFilter, userStatusFilter]);

  const refreshCoreTelemetry = useCallback(async () => {
    if (!isOwner) return;
    setRefreshing(true);
    try {
      const startIso = range === 'custom' && customStart ? new Date(customStart).toISOString() : undefined;
      const endIso = range === 'custom' && customEnd ? new Date(customEnd + 'T23:59:59Z').toISOString() : undefined;

      const [mon, ana, intel] = await Promise.all([
        fetchAdminMonitoring(),
        fetchAdminAnalytics(range, startIso, endIso),
        fetchAdminIntelligence(),
      ]);
      setMonitoring(mon);
      setAnalytics(ana);
      setIntelligence(intel);
      setConsoleError(null);
    } catch (err: any) {
      setConsoleError(err.message || 'Failed to refresh Control Centre telemetry');
    } finally {
      setRefreshing(false);
    }
  }, [isOwner, range, customStart, customEnd]);

  useEffect(() => {
    if (isOwner) {
      refreshCoreTelemetry();
    }
  }, [isOwner, range]);

  useEffect(() => {
    if (isOwner) {
      refreshUsers();
    }
  }, [isOwner, userPage, userSearch, userRoleFilter, userStatusFilter]);

  useEffect(() => {
    if (!isOwner || autoRefreshSeconds <= 0) return;
    const timer = window.setInterval(() => {
      refreshCoreTelemetry();
    }, autoRefreshSeconds * 1000);
    return () => window.clearInterval(timer);
  }, [isOwner, autoRefreshSeconds, refreshCoreTelemetry]);

  const handleAdminSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError(null);
    try {
      const data = await adminLogin(loginIdentifier, loginPassword, totpRequired ? loginTotp : undefined);
      setTotpRequired(false);
      setLoginTotp('');
      onAuthSuccess(data.user, data.access_token);
    } catch (err: any) {
      if (err instanceof TwoFactorRequiredError || err?.twoFactorRequired) {
        setTotpRequired(true);
      }
      setAuthError(err.message || 'Invalid owner credentials');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleBootstrapOwner = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError(null);
    try {
      const data = await bootstrapOwner(bootUsername, bootEmail, bootPassword, bootToken);
      onAuthSuccess(data.user, data.access_token);
      setBootstrapStatus({ owner_exists: true, requires_bootstrap_token: false, web_bootstrap_allowed: false });
    } catch (err: any) {
      setAuthError(err.message || 'Owner bootstrap failed');
    } finally {
      setAuthLoading(false);
    }
  };

  if (!isOwner) {
    const showBootstrap = bootstrapStatus && !bootstrapStatus.owner_exists && bootstrapStatus.web_bootstrap_allowed;
    return (
      <div className="min-h-screen bg-canvas text-ink flex flex-col justify-center items-center px-4 py-10">
        <div className="w-full max-w-md rounded-2xl border border-line bg-surface p-6 shadow-xl space-y-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/15 text-accent">
                <Shield className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-base font-semibold tracking-tight text-ink">AUREVON CONTROL CENTRE</h1>
                <p className="text-xs text-ink-muted">Private Owner Infrastructure Gate</p>
              </div>
            </div>
            <button
              type="button"
              onClick={onToggleTheme}
              className="rounded-lg border border-line p-1.5 text-ink-secondary hover:bg-elevated"
              title="Toggle theme"
            >
              {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
          </div>

          {currentUser && currentUser.role !== 'owner' ? (
            <div className="space-y-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs">
              <div className="flex items-center gap-2 font-semibold text-rose-500">
                <Lock className="h-4 w-4" />
                <span>Access Restricted — Owner Privileges Required</span>
              </div>
              <p className="text-ink-secondary leading-relaxed">
                Signed in as <strong className="text-ink">{currentUser.username}</strong> ({currentUser.role}). Only verified platform owners may access administrative operations or telemetry.
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={onExitAdmin}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 font-medium text-ink hover:bg-elevated"
                >
                  <ArrowLeft className="h-3.5 w-3.5" />
                  Return to Chat
                </button>
                <button
                  type="button"
                  onClick={onLogout}
                  className="rounded-lg bg-rose-600 px-3 py-1.5 font-medium text-white hover:bg-rose-500"
                >
                  Sign Out &amp; Switch Account
                </button>
              </div>
            </div>
          ) : showBootstrap ? (
            <form onSubmit={handleBootstrapOwner} className="space-y-3">
              <div className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 p-3 text-xs text-ink-secondary">
                No owner account exists yet. Create the sole initial administrator account below.
              </div>
              <input
                type="text"
                value={bootUsername}
                onChange={(e) => setBootUsername(e.target.value)}
                placeholder="Owner username"
                className="w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
                required
              />
              <input
                type="email"
                value={bootEmail}
                onChange={(e) => setBootEmail(e.target.value)}
                placeholder="Owner email"
                className="w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
                required
              />
              <input
                type="password"
                value={bootPassword}
                onChange={(e) => setBootPassword(e.target.value)}
                placeholder="Strong password (min 8 chars)"
                className="w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
                minLength={8}
                required
              />
              {bootstrapStatus?.requires_bootstrap_token && (
                <input
                  type="password"
                  value={bootToken}
                  onChange={(e) => setBootToken(e.target.value)}
                  placeholder="ADMIN_BOOTSTRAP_TOKEN"
                  className="w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
                  required
                />
              )}
              {authError && (
                <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-500">
                  {authError}
                </div>
              )}
              <button
                type="submit"
                disabled={authLoading}
                className="w-full rounded-lg bg-accent py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
              >
                {authLoading ? 'Bootstrapping Owner...' : 'Initialize Owner Account'}
              </button>
            </form>
          ) : (
            <form onSubmit={handleAdminSignIn} className="space-y-3">
              <div>
                <label className="block text-[11px] font-medium text-ink-secondary">Owner Email or Username</label>
                <input
                  type="text"
                  value={loginIdentifier}
                  onChange={(e) => setLoginIdentifier(e.target.value)}
                  placeholder="owner@aurevon.ai"
                  className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
                  required
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-ink-secondary">Password</label>
                <input
                  type="password"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  placeholder="••••••••"
                  className="mt-1 w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink"
                  required
                />
              </div>

              {totpRequired && (
                <div className="rounded-lg border border-indigo-500/40 bg-indigo-500/10 p-3 space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-indigo-400">
                    <KeyRound className="h-3.5 w-3.5" />
                    <span>Two-Factor Authentication Code</span>
                  </div>
                  <input
                    type="text"
                    maxLength={8}
                    value={loginTotp}
                    onChange={(e) => setLoginTotp(e.target.value)}
                    placeholder="6-digit code"
                    className="w-full rounded-lg border border-line bg-surface px-3 py-2 font-mono text-xs tracking-widest text-ink"
                    autoFocus
                    required
                  />
                </div>
              )}

              {authError && (
                <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-500">
                  {authError}
                </div>
              )}

              <button
                type="submit"
                disabled={authLoading}
                className="w-full rounded-lg bg-accent py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50 transition"
              >
                {authLoading ? 'Authenticating...' : totpRequired ? 'Verify Code & Sign In' : 'Sign In to Control Centre'}
              </button>
            </form>
          )}

          <div className="border-t border-line pt-3 flex justify-center">
            <button
              type="button"
              onClick={onExitAdmin}
              className="inline-flex items-center gap-1.5 text-xs text-ink-muted hover:text-ink transition"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to AUREVON Workspace
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <AdminLayout
      currentUser={currentUser}
      activeRoute={activeRoute}
      onNavigate={(next) => {
        setStatusNotice(null);
        setConsoleError(null);
        onNavigate(next);
      }}
      onExitAdmin={onExitAdmin}
      onLogout={onLogout}
      theme={theme}
      onToggleTheme={onToggleTheme}
      monitoring={monitoring}
      autoRefreshSeconds={autoRefreshSeconds}
      onChangeAutoRefresh={setAutoRefreshSeconds}
      onManualRefresh={() => {
        refreshCoreTelemetry();
        if (activeRoute === '/admin/users') refreshUsers();
      }}
      refreshing={refreshing}
    >
      {statusNotice && (
        <div className="flex items-center justify-between gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2.5 text-xs text-emerald-500">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span>{statusNotice}</span>
          </div>
          <button type="button" onClick={() => setStatusNotice(null)} aria-label="Dismiss notice">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {consoleError && (
        <div className="flex items-center justify-between gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-2.5 text-xs text-rose-500">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{consoleError}</span>
          </div>
          <button type="button" onClick={() => setConsoleError(null)} aria-label="Dismiss error">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {activeRoute === '/admin' && (
        <AdminDashboardPage
          analytics={analytics}
          range={range}
          onChangeRange={setRange}
          customStart={customStart}
          customEnd={customEnd}
          onChangeCustomStart={setCustomStart}
          onChangeCustomEnd={setCustomEnd}
          onApplyCustomRange={refreshCoreTelemetry}
          onNavigate={(next) => onNavigate(next)}
        />
      )}

      {activeRoute === '/admin/terminal' && <AdminTerminalPage />}

      {activeRoute === '/admin/ai' && (
        <AdminAIPage
          intelligence={intelligence}
          onUpdated={setIntelligence}
          onNotice={setStatusNotice}
          onError={setConsoleError}
        />
      )}

      {activeRoute === '/admin/users' && (
        <AdminUsersPage
          currentUserId={currentUser.id}
          usersData={usersData}
          page={userPage}
          search={userSearch}
          roleFilter={userRoleFilter}
          statusFilter={userStatusFilter}
          onChangePage={setUserPage}
          onChangeSearch={setUserSearch}
          onChangeRoleFilter={setUserRoleFilter}
          onChangeStatusFilter={setUserStatusFilter}
          onRefreshUsers={refreshUsers}
          onNotice={setStatusNotice}
          onError={setConsoleError}
        />
      )}

      {activeRoute === '/admin/system' && (
        <AdminSystemPage monitoring={monitoring} onError={setConsoleError} />
      )}

      {activeRoute === '/admin/logs' && (
        <AdminLogsPage onNotice={setStatusNotice} onError={setConsoleError} />
      )}

      {activeRoute === '/admin/security' && (
        <AdminSecurityPage onNotice={setStatusNotice} onError={setConsoleError} />
      )}

      {activeRoute === '/admin/settings' && (
        <AdminSettingsPage onNotice={setStatusNotice} onError={setConsoleError} />
      )}
    </AdminLayout>
  );
};
