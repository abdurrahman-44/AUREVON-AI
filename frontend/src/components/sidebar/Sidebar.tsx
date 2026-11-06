import React, { useState } from 'react';
import {
  Plus,
  MessageSquare,
  Search,
  Trash2,
  Edit2,
  Check,
  X,
  ChevronLeft,
  ChevronRight,
  Database,
  Cpu,
  RefreshCw,
} from 'lucide-react';
import { Conversation, SystemStatus } from '../../types';

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
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  const filteredConversations = conversations.filter((c) =>
    c.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

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

  const ollamaProvider = systemStatus?.providers.find((p) => p.provider === 'ollama');
  const isOllamaHealthy = ollamaProvider?.status === 'healthy';

  if (isCollapsed) {
    return (
      <aside className="w-16 bg-charcoal-900 border-r border-charcoal-800 flex flex-col items-center py-4 justify-between transition-all select-none">
        <div className="flex flex-col items-center gap-4">
          <button
            onClick={() => setIsCollapsed(false)}
            className="p-2 rounded-xl hover:bg-charcoal-800 text-charcoal-300 hover:text-white transition-colors"
            title="Expand Sidebar"
          >
            <ChevronRight size={18} />
          </button>
          <button
            onClick={onNewChat}
            className="p-3 rounded-xl bg-brand-600 hover:bg-brand-500 text-white transition-all shadow-md shadow-brand-600/30"
            title="New Conversation"
          >
            <Plus size={18} />
          </button>
        </div>

        {/* Minimized status indicators */}
        <div className="flex flex-col items-center gap-2">
          <div
            className={`w-2.5 h-2.5 rounded-full ${
              systemStatus?.database === 'connected' ? 'bg-emerald-500' : 'bg-rose-500'
            }`}
            title={`Database: ${systemStatus?.database || 'unknown'}`}
          />
          <div
            className={`w-2.5 h-2.5 rounded-full ${isOllamaHealthy ? 'bg-emerald-500' : 'bg-amber-500'}`}
            title={`Ollama: ${ollamaProvider?.status || 'offline'}`}
          />
        </div>
      </aside>
    );
  }

  return (
    <aside className="w-64 sm:w-72 bg-charcoal-900 border-r border-charcoal-800 flex flex-col justify-between transition-all select-none h-full">
      {/* Top Section */}
      <div className="p-3 flex flex-col gap-3">
        {/* Header with Logo */}
        <div className="flex items-center justify-between px-2 pt-1">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-charcoal-800 border border-charcoal-700/80 p-1 flex items-center justify-center">
              <img src="/logo.svg" alt="AUREVON" className="w-full h-full" />
            </div>
            <span className="font-bold tracking-tight text-white text-sm">AUREVON AI</span>
          </div>
          <button
            onClick={() => setIsCollapsed(true)}
            className="p-1.5 rounded-lg hover:bg-charcoal-800 text-charcoal-400 hover:text-charcoal-200 transition-colors"
            title="Collapse Sidebar"
          >
            <ChevronLeft size={16} />
          </button>
        </div>

        {/* New Chat Button */}
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold tracking-wide transition-all shadow-md shadow-brand-600/20"
        >
          <Plus size={15} />
          <span>New Conversation</span>
        </button>

        {/* Search Conversations */}
        <div className="relative">
          <Search size={14} className="absolute left-3 top-2.5 text-charcoal-500 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search chats..."
            className="w-full bg-charcoal-800/60 border border-charcoal-700/50 rounded-xl pl-8 pr-3 py-1.5 text-xs text-charcoal-200 placeholder-charcoal-500 focus:outline-none focus:border-charcoal-600 transition-colors"
          />
        </div>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
        <div className="px-2 py-1 text-[11px] font-semibold uppercase tracking-wider text-charcoal-500">
          History ({filteredConversations.length})
        </div>

        {filteredConversations.length === 0 ? (
          <div className="px-3 py-6 text-center text-xs text-charcoal-500">
            {searchQuery ? 'No matching conversations' : 'No conversations yet'}
          </div>
        ) : (
          filteredConversations.map((conv) => {
            const isActive = conv.id === activeConversationId;
            const isEditing = conv.id === editingId;

            return (
              <div
                key={conv.id}
                onClick={() => onSelectConversation(conv.id)}
                className={`group relative flex items-center justify-between px-3 py-2 rounded-xl text-xs cursor-pointer transition-all ${
                  isActive
                    ? 'bg-charcoal-800 text-white font-medium border border-charcoal-700/80 shadow-sm'
                    : 'text-charcoal-300 hover:bg-charcoal-800/50 hover:text-charcoal-100'
                }`}
              >
                {isEditing ? (
                  <form
                    onSubmit={(e) => saveEditing(conv.id, e)}
                    className="flex items-center gap-1 w-full"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      autoFocus
                      className="flex-1 bg-charcoal-900 border border-brand-500 rounded px-1.5 py-0.5 text-xs text-white focus:outline-none"
                    />
                    <button
                      type="submit"
                      className="p-1 text-emerald-400 hover:text-emerald-300"
                      title="Save"
                    >
                      <Check size={13} />
                    </button>
                    <button
                      type="button"
                      onClick={cancelEditing}
                      className="p-1 text-charcoal-400 hover:text-charcoal-200"
                      title="Cancel"
                    >
                      <X size={13} />
                    </button>
                  </form>
                ) : (
                  <>
                    <div className="flex items-center gap-2 min-w-0 pr-2">
                      <MessageSquare
                        size={14}
                        className={isActive ? 'text-brand-400 flex-shrink-0' : 'text-charcoal-500 flex-shrink-0'}
                      />
                      <span className="truncate">{conv.title}</span>
                    </div>

                    {/* Actions */}
                    <div className="opacity-0 group-hover:opacity-100 flex items-center gap-0.5 transition-opacity">
                      <button
                        onClick={(e) => startEditing(conv, e)}
                        className="p-1 rounded text-charcoal-400 hover:text-charcoal-200 hover:bg-charcoal-700/50"
                        title="Rename conversation"
                      >
                        <Edit2 size={12} />
                      </button>
                      <button
                        onClick={(e) => handleDelete(conv.id, e)}
                        className="p-1 rounded text-charcoal-400 hover:text-rose-400 hover:bg-charcoal-700/50"
                        title="Delete conversation"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* System Status Footer */}
      <div className="p-3 border-t border-charcoal-800 bg-charcoal-900/80">
        <div className="flex items-center justify-between text-[11px] text-charcoal-400 mb-2">
          <span className="font-semibold uppercase tracking-wider">System Status</span>
          <button
            onClick={onRefreshHealth}
            className="hover:text-charcoal-200 p-0.5 transition-colors"
            title="Refresh System Health"
          >
            <RefreshCw size={11} />
          </button>
        </div>

        <div className="space-y-1.5 text-xs">
          <div className="flex items-center justify-between px-2 py-1 rounded bg-charcoal-800/50">
            <span className="flex items-center gap-1.5 text-charcoal-300">
              <Database size={12} className="text-charcoal-400" />
              <span>Database</span>
            </span>
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-medium ${
                systemStatus?.database === 'connected'
                  ? 'bg-emerald-500/20 text-emerald-400'
                  : 'bg-rose-500/20 text-rose-400'
              }`}
            >
              {systemStatus?.database || 'checking'}
            </span>
          </div>

          <div className="flex items-center justify-between px-2 py-1 rounded bg-charcoal-800/50">
            <span className="flex items-center gap-1.5 text-charcoal-300">
              <Cpu size={12} className="text-charcoal-400" />
              <span>Ollama AI</span>
            </span>
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-medium ${
                isOllamaHealthy
                  ? 'bg-emerald-500/20 text-emerald-400'
                  : 'bg-amber-500/20 text-amber-400'
              }`}
            >
              {ollamaProvider?.status || 'offline'}
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
};
