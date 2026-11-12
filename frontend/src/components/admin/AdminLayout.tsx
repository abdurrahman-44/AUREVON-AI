import React, { useState } from 'react';
import {
  Activity,
  ArrowLeft,
  Cpu,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  RefreshCw,
  ScrollText,
  Server,
  Shield,
  ShieldCheck,
  Sliders,
  Sun,
  Terminal,
  Users,
  X,
} from 'lucide-react';
import { AdminSectionRoute, SystemMonitoringResponse, User } from '../../types';

export interface MetricTileProps {
  label: string;
  value: string | number;
  sublabel?: string;
  tone?: 'default' | 'good' | 'warn' | 'bad';
}

export const MetricTile: React.FC<MetricTileProps> = ({
  label,
  value,
  sublabel,
  tone = 'default',
}) => {
  const toneClass =
    tone === 'good'
      ? 'text-emerald-600 dark:text-emerald-400'
      : tone === 'warn'
        ? 'text-amber-600 dark:text-amber-400'
        : tone === 'bad'
          ? 'text-rose-600 dark:text-rose-400'
          : 'text-ink';

  return (
    <div className="rounded-xl border border-line bg-surface p-4 shadow-sm">
      <div className="text-[11px] font-medium uppercase tracking-wider text-ink-muted">{label}</div>
      <div className={`mt-1.5 text-2xl font-semibold tracking-tight ${toneClass}`}>{value}</div>
      {sublabel && <div className="mt-1 text-xs text-ink-secondary">{sublabel}</div>}
    </div>
  );
};

interface NavItem {
  route: AdminSectionRoute;
  label: string;
  description: string;
  icon: React.FC<{ className?: string }>;
}

const NAV_ITEMS: NavItem[] = [
  { route: '/admin', label: 'Overview', description: 'KPIs & telemetry charts', icon: LayoutDashboard },
  { route: '/admin/terminal', label: 'Terminal', description: 'Allowlisted ops shell', icon: Terminal },
  { route: '/admin/ai', label: 'AI & Models', description: 'Core config & live probe', icon: Cpu },
  { route: '/admin/users', label: 'Users', description: 'Accounts & RBAC', icon: Users },
  { route: '/admin/system', label: 'System', description: 'Health, host & diagnostics', icon: Server },
  { route: '/admin/logs', label: 'Logs & Audit', description: 'API, errors & audit trail', icon: ScrollText },
  { route: '/admin/security', label: 'Security & 2FA', description: 'TOTP & security events', icon: ShieldCheck },
  { route: '/admin/settings', label: 'Settings', description: 'Maintenance & policies', icon: Sliders },
];

interface AdminLayoutProps {
  currentUser: User;
  activeRoute: AdminSectionRoute;
  onNavigate: (path: AdminSectionRoute) => void;
  onExitAdmin: () => void;
  onLogout: () => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  monitoring: SystemMonitoringResponse | null;
  autoRefreshSeconds: number;
  onChangeAutoRefresh: (sec: number) => void;
  onManualRefresh: () => void;
  refreshing: boolean;
  children: React.ReactNode;
}

export const AdminLayout: React.FC<AdminLayoutProps> = ({
  currentUser,
  activeRoute,
  onNavigate,
  onExitAdmin,
  onLogout,
  theme,
  onToggleTheme,
  monitoring,
  autoRefreshSeconds,
  onChangeAutoRefresh,
  onManualRefresh,
  refreshing,
  children,
}) => {
  const [mobileOpen, setMobileOpen] = useState(false);

  const activeNav = NAV_ITEMS.find((n) => n.route === activeRoute) || NAV_ITEMS[0];
  const backendHealthy = monitoring?.backend_status === 'healthy' && monitoring?.database_connected;

  const handleSelectRoute = (route: AdminSectionRoute) => {
    onNavigate(route);
    setMobileOpen(false);
  };

  const renderSidebarBody = () => (
    <div className="flex h-full flex-col">
      <div className="flex h-14 items-center justify-between border-b border-line px-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/15 text-accent">
            <Shield className="h-4 w-4" />
          </div>
          <div>
            <div className="text-xs font-semibold tracking-wide text-ink">AUREVON</div>
            <div className="text-[10px] font-medium uppercase tracking-widest text-ink-muted">Control Centre</div>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setMobileOpen(false)}
          className="rounded-lg p-1 text-ink-muted hover:bg-elevated lg:hidden"
          aria-label="Close sidebar"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-2.5 py-3">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeRoute === item.route;
          return (
            <button
              key={item.route}
              type="button"
              onClick={() => handleSelectRoute(item.route)}
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition ${
                isActive
                  ? 'bg-accent/15 text-ink ring-1 ring-accent/30'
                  : 'text-ink-secondary hover:bg-elevated hover:text-ink'
              }`}
            >
              <Icon className={`h-4 w-4 shrink-0 ${isActive ? 'text-accent' : 'text-ink-muted'}`} />
              <div className="min-w-0">
                <div className="truncate text-xs font-semibold">{item.label}</div>
                <div className="truncate text-[10px] text-ink-muted">{item.description}</div>
              </div>
            </button>
          );
        })}
      </nav>

      <div className="border-t border-line p-3 space-y-2">
        <div className="rounded-lg border border-line bg-elevated/60 px-3 py-2">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-ink-muted">Owner Session</span>
            <span className="font-semibold text-accent uppercase">{currentUser.role}</span>
          </div>
          <div className="mt-0.5 truncate text-xs font-medium text-ink">{currentUser.username}</div>
          <div className="truncate text-[11px] text-ink-muted">{currentUser.email}</div>
        </div>

        <button
          type="button"
          onClick={onExitAdmin}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-ink-secondary hover:bg-elevated hover:text-ink transition"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Return to Workspace
        </button>

        <button
          type="button"
          onClick={onLogout}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-rose-500 hover:bg-rose-500/10 transition"
        >
          <LogOut className="h-3.5 w-3.5" />
          Sign Out
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen w-full overflow-hidden bg-canvas text-ink">
      <aside className="hidden w-60 shrink-0 border-r border-line bg-surface lg:block">
        {renderSidebarBody()}
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-xs"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="relative z-10 w-64 border-r border-line bg-surface">
            {renderSidebarBody()}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-line bg-surface/90 px-4 backdrop-blur">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="rounded-lg border border-line p-1.5 text-ink-secondary hover:bg-elevated lg:hidden"
              aria-label="Open navigation"
            >
              <Menu className="h-4 w-4" />
            </button>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="truncate text-sm font-semibold text-ink">{activeNav.label}</h1>
                <span className="hidden text-xs text-ink-muted sm:inline">— {activeNav.description}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {monitoring && (
              <div
                className={`hidden items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium md:flex ${
                  backendHealthy
                    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-500'
                    : 'border-amber-500/30 bg-amber-500/10 text-amber-500'
                }`}
              >
                <Activity className="h-3 w-3" />
                <span>{backendHealthy ? 'Operational' : monitoring.backend_status}</span>
                <span className="text-ink-muted">•</span>
                <span className="text-ink">{monitoring.active_model}</span>
              </div>
            )}

            <select
              aria-label="Auto refresh interval"
              value={autoRefreshSeconds}
              onChange={(e) => onChangeAutoRefresh(Number(e.target.value))}
              className="rounded-lg border border-line bg-elevated px-2 py-1 text-xs text-ink-secondary focus:outline-none"
            >
              <option value={0}>Auto: Off</option>
              <option value={15}>Auto: 15s</option>
              <option value={30}>Auto: 30s</option>
              <option value={60}>Auto: 60s</option>
            </select>

            <button
              type="button"
              onClick={onManualRefresh}
              disabled={refreshing}
              className="flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-xs font-medium text-ink-secondary hover:bg-elevated hover:text-ink disabled:opacity-50 transition"
              title="Refresh telemetry"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">Refresh</span>
            </button>

            <button
              type="button"
              onClick={onToggleTheme}
              className="rounded-lg border border-line p-1.5 text-ink-secondary hover:bg-elevated hover:text-ink transition"
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
            >
              {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto px-4 py-5 md:px-6">
          <div className="mx-auto max-w-7xl space-y-6">{children}</div>
        </main>
      </div>
    </div>
  );
};
