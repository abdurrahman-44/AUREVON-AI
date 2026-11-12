import React, { useState } from 'react';
import {
  Bot,
  Brain,
  Check,
  ChevronLeft,
  ChevronRight,
  Edit2,
  FileText,
  Globe,
  LogIn,
  LogOut,
  MessageSquare,
  Moon,
  Plus,
  RefreshCw,
  Search,
  Settings as SettingsIcon,
  Shield,
  Sun,
  Trash2,
  User as UserIcon,
  X,
} from 'lucide-react';
import { Conversation, SystemStatus, User } from '../../types';

interface SidebarProps {
  conversations: Conversation[];
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewChat: () => void;
  onRenameConversation: (id: string, newTitle: string) => void;
  onDeleteConversation: (id: string) => void;
  systemStatus: SystemStatus | null;
  onRefreshHealth: () => void;
  isCollapsed: boolean;
  setIsCollapsed: (collapsed: boolean) => void;
  currentUser: User | null;
  onOpenAuth: () => void;
  onOpenSettings: () => void;
  onLogout: () => void;
  onOpenDocuments: () => void;
  onOpenMemory: () => void;
  onOpenResearch: () => void;
  onOpenAgents: () => void;
  onOpenAdmin?: () => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewChat,
  onRenameConversation,
  onDeleteConversation,
  systemStatus,
  onRefreshHealth,
  isCollapsed,
  setIsCollapsed,
  currentUser,
  onOpenAuth,
  onOpenSettings,
  onLogout,
  onOpenDocuments,
  onOpenMemory,
  onOpenResearch,
  onOpenAgents,
  onOpenAdmin,
  theme,
  onToggleTheme,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  const filteredConversations = conversations.filter((c) =>
    c.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const isOwner = currentUser?.role === 'owner';
  const ollamaProvider = systemStatus?.providers?.find((p) => p.provider === 'ollama');
  const isProviderOnline = ollamaProvider?.status === 'healthy';

  const startEditing = (conv: Conversation, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(conv.id);
    setEditTitle(conv.title);
  };

  const saveEditing = (id: string, e: React.MouseEvent | React.FormEvent) => {
    e.stopPropagation();
    if (editTitle.trim()) {
      onRenameConversation(id, editTitle.trim());
    }
    setEditingId(null);
  };

  const cancelEditing = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(null);
  };

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Delete this conversation?')) {
      onDeleteConversation(id);
    }
  };

  if (isCollapsed) {
    return (
      <aside className="w-14 h-full border-r border-line bg-surface flex flex-col items-center py-3.5 justify-between shrink-0">
        <div className="flex flex-col items-center gap-2.5">
          <button
            onClick={() => setIsCollapsed(false)}
            className="p-2 rounded-lg text-ink-secondary hover:text-ink hover:bg-elevated transition-colors"
            title="Expand sidebar"
          >
            <ChevronRight size={18} />
          </button>
          <button
            onClick={onNewChat}
            className="p-2 rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors"
            title="New conversation"
          >
            <Plus size={18} />
          </button>

          <div className="w-6 border-t border-line my-1" />

          <button onClick={onOpenDocuments} className="p-2 rounded-lg text-ink-secondary hover:text-ink hover:bg-elevated" title="Documents">
            <FileText size={16} />
          </button>
          <button onClick={onOpenMemory} className="p-2 rounded-lg text-ink-secondary hover:text-ink hover:bg-elevated" title="Memory">
            <Brain size={16} />
          </button>
          <button onClick={onOpenResearch} className="p-2 rounded-lg text-ink-secondary hover:text-ink hover:bg-elevated" title="Web Research">
            <Globe size={16} />
          </button>
          <button onClick={onOpenAgents} className="p-2 rounded-lg text-ink-secondary hover:text-ink hover:bg-elevated" title="Agents">
            <Bot size={16} />
          </button>
          {isOwner && onOpenAdmin && (
            <button onClick={onOpenAdmin} className="p-2 rounded-lg text-accent hover:bg-accent/10" title="Owner Console">
              <Shield size={16} />
            </button>
          )}
        </div>

        <div className="flex flex-col items-center gap-2">
          <button
            onClick={onToggleTheme}
            className="p-2 rounded-lg text-ink-secondary hover:text-ink hover:bg-elevated"
            title="Toggle theme"
          >
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          </button>
          <button
            onClick={currentUser ? onOpenSettings : onOpenAuth}
            className="p-2 rounded-lg text-ink-secondary hover:text-ink hover:bg-elevated"
            title={currentUser ? currentUser.username : 'Sign in'}
          >
            <UserIcon size={16} />
          </button>
        </div>
      </aside>
    );
  }

  return (
    <aside className="w-72 h-full border-r border-line bg-surface flex flex-col shrink-0">
      {/* Brand Header */}
      <div className="px-4 py-3.5 border-b border-line flex items-center justify-between">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center text-white text-xs font-semibold tracking-tight shrink-0">
            A
          </div>
          <div className="min-w-0">
            <span className="block text-sm font-semibold tracking-tight text-ink leading-none">AUREVON</span>
            <span className="block text-[10px] text-ink-muted mt-1 leading-none">Intelligence Platform</span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onToggleTheme}
            className="p-1.5 rounded-lg text-ink-secondary hover:text-ink hover:bg-elevated transition-colors"
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
          </button>
          <button
            onClick={() => setIsCollapsed(true)}
            className="p-1.5 rounded-lg text-ink-secondary hover:text-ink hover:bg-elevated transition-colors"
            title="Collapse sidebar"
          >
            <ChevronLeft size={16} />
          </button>
        </div>
      </div>

      {/* Primary Action */}
      <div className="p-3 pb-2 space-y-2.5">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-xl bg-accent hover:bg-accent-hover text-white text-xs font-medium transition-colors"
        >
          <Plus size={15} />
          New Conversation
        </button>

        {/* Workspace Modules */}
        <div className="grid grid-cols-4 gap-1 pt-0.5">
          <ToolButton icon={<FileText size={14} />} label="Docs" onClick={onOpenDocuments} />
          <ToolButton icon={<Brain size={14} />} label="Memory" onClick={onOpenMemory} />
          <ToolButton icon={<Globe size={14} />} label="Search" onClick={onOpenResearch} />
          <ToolButton icon={<Bot size={14} />} label="Agents" onClick={onOpenAgents} />
        </div>

        {/* Owner-Only Console Link */}
        {isOwner && onOpenAdmin && (
          <button
            onClick={onOpenAdmin}
            className="w-full flex items-center justify-between px-3 py-2 rounded-xl border border-accent/25 bg-accent/10 text-accent hover:bg-accent/15 text-xs font-medium transition-colors"
          >
            <span className="inline-flex items-center gap-2">
              <Shield size={14} />
              Owner Console
            </span>
            <span className="text-[10px] font-mono opacity-80">/admin</span>
          </button>
        )}

        {/* Search Conversations */}
        <div className="relative">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter conversations..."
            className="w-full pl-8 pr-3 py-1.5 rounded-lg border border-line bg-canvas text-xs text-ink placeholder-ink-muted focus:outline-none focus:border-line-strong"
          />
        </div>
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto px-2.5 py-1 space-y-0.5">
        {filteredConversations.length === 0 ? (
          <div className="px-3 py-8 text-center text-xs text-ink-muted">
            {searchQuery ? 'No matching threads' : 'No conversations yet'}
          </div>
        ) : (
          filteredConversations.map((conv) => {
            const isActive = conv.id === activeConversationId;
            const isEditing = editingId === conv.id;

            return (
              <div
                key={conv.id}
                onClick={() => !isEditing && onSelectConversation(conv.id)}
                className={`group flex items-center justify-between px-2.5 py-2 rounded-xl cursor-pointer transition-colors ${
                  isActive
                    ? 'bg-elevated text-ink'
                    : 'text-ink-secondary hover:bg-elevated/60 hover:text-ink'
                }`}
              >
                {isEditing ? (
                  <form
                    onSubmit={(e) => saveEditing(conv.id, e)}
                    className="flex items-center gap-1 w-full"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <input
                      autoFocus
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="flex-1 px-2 py-0.5 text-xs rounded border border-line-strong bg-canvas text-ink focus:outline-none"
                    />
                    <button type="submit" className="p-1 text-emerald-500 hover:bg-surface rounded">
                      <Check size={12} />
                    </button>
                    <button type="button" onClick={cancelEditing} className="p-1 text-ink-muted hover:bg-surface rounded">
                      <X size={12} />
                    </button>
                  </form>
                ) : (
                  <>
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <MessageSquare size={13} className="text-ink-muted shrink-0" />
                      <span className="text-xs truncate">{conv.title}</span>
                    </div>
                    <div className="opacity-0 group-hover:opacity-100 flex items-center gap-0.5 shrink-0 transition-opacity">
                      <button
                        onClick={(e) => startEditing(conv, e)}
                        className="p-1 rounded text-ink-muted hover:text-ink hover:bg-surface"
                        title="Rename"
                      >
                        <Edit2 size={11} />
                      </button>
                      <button
                        onClick={(e) => handleDelete(conv.id, e)}
                        className="p-1 rounded text-ink-muted hover:text-rose-500 hover:bg-surface"
                        title="Delete"
                      >
                        <Trash2 size={11} />
                      </button>
                    </div>
                  </>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Footer Profile & Health */}
      <div className="p-3 border-t border-line space-y-2.5 bg-surface">
        <div className="flex items-center justify-between gap-2 px-2.5 py-2 rounded-xl border border-line bg-canvas">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded-lg bg-elevated border border-line flex items-center justify-center text-ink-secondary shrink-0">
              <UserIcon size={14} />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-medium text-ink truncate">
                  {currentUser ? currentUser.username : 'Guest Session'}
                </span>
                {isOwner && (
                  <span className="px-1.5 py-0.2 rounded bg-accent/15 text-accent text-[9px] font-medium uppercase">
                    Owner
                  </span>
                )}
              </div>
              <span className="block text-[10px] text-ink-muted truncate">
                {currentUser ? currentUser.email : 'Local workspace'}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            {currentUser ? (
              <>
                <button
                  onClick={onOpenSettings}
                  className="p-1.5 rounded-lg text-ink-secondary hover:text-ink hover:bg-elevated transition-colors"
                  title="Preferences"
                >
                  <SettingsIcon size={13} />
                </button>
                <button
                  onClick={onLogout}
                  className="p-1.5 rounded-lg text-ink-secondary hover:text-rose-500 hover:bg-elevated transition-colors"
                  title="Sign out"
                >
                  <LogOut size={13} />
                </button>
              </>
            ) : (
              <button
                onClick={onOpenAuth}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-elevated hover:bg-muted text-ink text-[11px] font-medium transition-colors"
              >
                <LogIn size={11} />
                Sign In
              </button>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between px-1 text-[11px] text-ink-muted">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5">
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isProviderOnline ? 'bg-emerald-500' : 'bg-amber-500'
                }`}
              />
              <span>{isProviderOnline ? 'Runtime ready' : 'Runtime offline'}</span>
            </span>
          </div>
          <button
            onClick={onRefreshHealth}
            className="p-1 rounded hover:text-ink transition-colors"
            title="Refresh connection status"
          >
            <RefreshCw size={11} />
          </button>
        </div>
      </div>
    </aside>
  );
};

const ToolButton: React.FC<{ icon: React.ReactNode; label: string; onClick: () => void }> = ({
  icon,
  label,
  onClick,
}) => (
  <button
    type="button"
    onClick={onClick}
    className="flex flex-col items-center justify-center gap-1 py-2 px-1 rounded-lg border border-line bg-canvas hover:bg-elevated text-ink-secondary hover:text-ink transition-colors"
  >
    {icon}
    <span className="text-[10px] font-medium">{label}</span>
  </button>
);
