import React, { useEffect, useRef, useState } from 'react';
import { Sidebar } from './components/sidebar/Sidebar';
import { ChatMessage } from './components/chat/ChatMessage';
import { WelcomeScreen } from './components/chat/WelcomeScreen';
import { Composer } from './components/composer/Composer';
import { AuthModal } from './components/auth/AuthModal';
import { SettingsModal } from './components/settings/SettingsModal';
import { ModelManagementModal } from './components/models/ModelManagementModal';
import { DocumentsModal } from './components/documents/DocumentsModal';
import { MemoryModal } from './components/memory/MemoryModal';
import { ResearchModal } from './components/research/ResearchModal';
import { AgentModal } from './components/agents/AgentModal';
import { AdminConsole } from './components/admin/AdminConsole';
import {
  deleteConversation,
  fetchConversation,
  fetchConversations,
  fetchMe,
  fetchModels,
  fetchPublicIntelligence,
  fetchSystemHealth,
  logoutUser,
  streamChat,
  updateConversationTitle,
} from './services/api';
import {
  CitationItem,
  Conversation,
  Message,
  ModelInfo,
  PublicIntelligenceConfig,
  SystemStatus,
  ToolCallEvent,
  User,
  UserSettings,
} from './types';

export const App: React.FC = () => {
  const [routePath, setRoutePath] = useState<string>(() => window.location.pathname || '/');
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [streamingStatus, setStreamingStatus] = useState<string | null>(null);
  const [streamingTools, setStreamingTools] = useState<ToolCallEvent[]>([]);
  const [streamingCitations, setStreamingCitations] = useState<CitationItem[]>([]);
  const [streamingCharts, setStreamingCharts] = useState<string[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('qwen2.5:3b');
  const [publicIntelligence, setPublicIntelligence] = useState<PublicIntelligenceConfig | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('aurevon_theme');
    return saved === 'light' ? 'light' : 'dark';
  });

  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [userSettings, setUserSettings] = useState<UserSettings | null>(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [isModelModalOpen, setIsModelModalOpen] = useState(false);
  const [isDocumentsModalOpen, setIsDocumentsModalOpen] = useState(false);
  const [isMemoryModalOpen, setIsMemoryModalOpen] = useState(false);
  const [isResearchModalOpen, setIsResearchModalOpen] = useState(false);
  const [isAgentModalOpen, setIsAgentModalOpen] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const navigate = (path: string) => {
    if (window.location.pathname !== path) {
      window.history.pushState({}, '', path);
    }
    setRoutePath(path);
  };

  useEffect(() => {
    const handlePop = () => setRoutePath(window.location.pathname || '/');
    window.addEventListener('popstate', handlePop);
    return () => window.removeEventListener('popstate', handlePop);
  }, []);

  useEffect(() => {
    loadInitialData();
  }, []);

  useEffect(() => {
    const prefTheme = userSettings?.theme;
    let resolved: 'light' | 'dark' = theme;
    if (prefTheme === 'light' || prefTheme === 'dark') {
      resolved = prefTheme;
    } else if (prefTheme === 'system') {
      resolved = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    document.documentElement.classList.toggle('dark', resolved === 'dark');
    document.documentElement.classList.toggle('light', resolved === 'light');
  }, [theme, userSettings?.theme]);

  const handleToggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    localStorage.setItem('aurevon_theme', next);
    if (userSettings) {
      setUserSettings({ ...userSettings, theme: next });
    }
  };

  const loadInitialData = async () => {
    let loadedSettings: UserSettings | null = null;
    const token = localStorage.getItem('aurevon_token');
    if (token) {
      try {
        const user = await fetchMe();
        setCurrentUser(user);
        if (user.settings) {
          loadedSettings = user.settings;
          setUserSettings(user.settings);
          if (user.settings.theme === 'light' || user.settings.theme === 'dark') {
            setTheme(user.settings.theme);
          }
        }
      } catch {
        localStorage.removeItem('aurevon_token');
        setCurrentUser(null);
      }
    }

    try {
      const [convs, modelList, health, pubIntel] = await Promise.all([
        fetchConversations().catch(() => []),
        fetchModels().catch(() => []),
        fetchSystemHealth().catch(() => null),
        fetchPublicIntelligence().catch(() => null),
      ]);

      setConversations(convs);
      setModels(modelList);
      if (health) setSystemStatus(health);
      if (pubIntel) {
        setPublicIntelligence(pubIntel);
        if (!pubIntel.allow_user_model_switching) {
          setSelectedModel(pubIntel.active_model);
        } else if (loadedSettings?.default_model) {
          setSelectedModel(loadedSettings.default_model);
        } else {
          setSelectedModel(pubIntel.active_model);
        }
      }
    } catch (err) {
      console.error('Error loading initial data:', err);
    }
  };

  const handleAuthSuccess = async (user: User, token: string) => {
    localStorage.setItem('aurevon_token', token);
    setCurrentUser(user);
    if (user.settings) {
      setUserSettings(user.settings);
      if (user.settings.theme === 'light' || user.settings.theme === 'dark') {
        setTheme(user.settings.theme);
      }
      if (publicIntelligence?.allow_user_model_switching && user.settings.default_model) {
        setSelectedModel(user.settings.default_model);
      }
    }
    try {
      const convs = await fetchConversations();
      setConversations(convs);
      setActiveConversationId(null);
      setMessages([]);
    } catch (e) {
      console.error('Failed to reload conversations:', e);
    }
  };

  const handleLogout = async () => {
    await logoutUser();
    localStorage.removeItem('aurevon_token');
    setCurrentUser(null);
    setUserSettings(null);
    handleNewChat();
    if (routePath.startsWith('/admin')) {
      navigate('/');
    }
    loadInitialData();
  };

  const handleSelectConversation = async (id: string) => {
    if (activeConversationId === id) return;
    try {
      const detail = await fetchConversation(id);
      setActiveConversationId(id);
      setMessages(detail.messages);
      setStreamingContent('');
    } catch (err) {
      console.error('Failed to load conversation messages:', err);
    }
  };

  const handleNewChat = () => {
    setActiveConversationId(null);
    setMessages([]);
    setInput('');
    setStreamingContent('');
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const handleRefreshHealth = async () => {
    try {
      const [h, modelList, pubIntel] = await Promise.all([
        fetchSystemHealth(),
        fetchModels(),
        fetchPublicIntelligence(),
      ]);
      setSystemStatus(h);
      setModels(modelList);
      setPublicIntelligence(pubIntel);
      if (!pubIntel.allow_user_model_switching) {
        setSelectedModel(pubIntel.active_model);
      }
    } catch (err) {
      console.error('Failed to refresh health:', err);
    }
  };

  const handleRename = async (id: string, newTitle: string) => {
    try {
      const updated = await updateConversationTitle(id, newTitle);
      setConversations((prev) =>
        prev.map((c) => (c.id === id ? { ...c, title: updated.title } : c))
      );
    } catch (err) {
      console.error('Failed to rename conversation:', err);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeConversationId === id) {
        handleNewChat();
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  const handleSend = async (
    customPrompt?: string,
    images?: string[],
    options?: { documentIds?: string[]; webSearch?: boolean; allowCloud?: boolean; regenerate?: boolean }
  ) => {
    const promptToSend = (customPrompt !== undefined ? customPrompt : input).trim();
    if ((!promptToSend && (!images || images.length === 0)) || isStreaming) return;

    if (!options?.regenerate) {
      setInput('');
      const tempUserMessage: Message = {
        id: `temp-${Date.now()}`,
        conversation_id: activeConversationId || '',
        role: 'user',
        content: promptToSend || '(Attached image)',
        model: selectedModel,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, tempUserMessage]);
    }

    setIsStreaming(true);
    setStreamingContent('');
    setStreamingStatus('analyzing');
    setStreamingTools([]);
    setStreamingCitations([]);
    setStreamingCharts([]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    let currentConversationId = activeConversationId;
    let accumulated = '';
    let resolvedModel = selectedModel;
    let resolvedIntent: string | null = null;
    let collectedTools: ToolCallEvent[] = [];
    let collectedCitations: CitationItem[] = [];
    let collectedCharts: string[] = [];

    try {
      await streamChat({
        conversationId: activeConversationId || undefined,
        message: promptToSend || 'Explain this image',
        model: selectedModel,
        images,
        documentIds: options?.documentIds,
        webSearch: options?.webSearch,
        allowCloud: options?.allowCloud,
        regenerate: options?.regenerate,
        abortSignal: controller.signal,
        onInit: (data) => {
          if (!currentConversationId && data.conversation_id) {
            currentConversationId = data.conversation_id;
            setActiveConversationId(data.conversation_id);
          }
          if (data.model) {
            resolvedModel = data.model;
            setSelectedModel(data.model);
          }
          if (data.intent) {
            resolvedIntent = data.intent;
          }
        },
        onStatus: (st) => {
          setStreamingStatus(st);
        },
        onToolEvent: (ev) => {
          collectedTools = [...collectedTools, ev];
          setStreamingTools(collectedTools);
        },
        onCitations: (cits) => {
          collectedCitations = cits;
          setStreamingCitations(cits);
        },
        onCharts: (charts) => {
          collectedCharts = [...collectedCharts, ...charts];
          setStreamingCharts(collectedCharts);
        },
        onChunk: (delta) => {
          accumulated += delta;
          setStreamingContent(accumulated);
        },
        onDone: async (data) => {
          setIsStreaming(false);
          const finalAssistantMsg: Message = {
            id: data.assistant_message_id || `asst-${Date.now()}`,
            conversation_id: data.conversation_id,
            role: 'assistant',
            content: accumulated,
            model: data.model || resolvedModel,
            token_usage: data.token_usage || null,
            tool_calls: data.tools_used || (collectedTools.length > 0 ? collectedTools : null),
            citations: data.citations || (collectedCitations.length > 0 ? collectedCitations : null),
            charts: collectedCharts.length > 0 ? collectedCharts : null,
            intent: data.intent || resolvedIntent,
            created_at: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, finalAssistantMsg]);
          setStreamingContent('');
          setStreamingStatus(null);
          setStreamingTools([]);
          setStreamingCitations([]);
          setStreamingCharts([]);

          const updatedConvs = await fetchConversations();
          setConversations(updatedConvs);
        },
        onError: (err) => {
          setIsStreaming(false);
          setStreamingContent('');
          setStreamingStatus(null);
          setMessages((prev) => [
            ...prev,
            {
              id: `err-${Date.now()}`,
              conversation_id: currentConversationId || '',
              role: 'assistant',
              content: `**Request failed**: ${err.message}`,
              created_at: new Date().toISOString(),
            },
          ]);
        },
      });
    } catch {
      setIsStreaming(false);
      setStreamingContent('');
      setStreamingStatus(null);
    }
  };

  const handleRegenerateLast = () => {
    if (isStreaming || messages.length === 0) return;
    const lastUser = [...messages].reverse().find((m) => m.role === 'user');
    if (!lastUser) return;
    // Remove trailing assistant message from UI state cleanly before re-streaming
    setMessages((prev) => {
      if (prev.length > 0 && prev[prev.length - 1].role === 'assistant') {
        return prev.slice(0, -1);
      }
      return prev;
    });
    handleSend(lastUser.content, undefined, { regenerate: true });
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (streamingContent) {
      setMessages((prev) => [
        ...prev,
        {
          id: `asst-stop-${Date.now()}`,
          conversation_id: activeConversationId || '',
          role: 'assistant',
          content: streamingContent + ' *(Stopped)*',
          model: selectedModel,
          tool_calls: streamingTools.length > 0 ? streamingTools : null,
          citations: streamingCitations.length > 0 ? streamingCitations : null,
          charts: streamingCharts.length > 0 ? streamingCharts : null,
          created_at: new Date().toISOString(),
        },
      ]);
    }
    setIsStreaming(false);
    setStreamingContent('');
  };

  if (routePath.startsWith('/admin')) {
    return (
      <AdminConsole
        currentUser={currentUser}
        routePath={routePath}
        onNavigate={navigate}
        onAuthSuccess={handleAuthSuccess}
        onExitAdmin={() => {
          navigate('/');
          handleRefreshHealth();
        }}
        onLogout={handleLogout}
        theme={theme}
        onToggleTheme={handleToggleTheme}
      />
    );
  }

  const allowSwitching = Boolean(publicIntelligence?.allow_user_model_switching);
  const isOwner = currentUser?.role === 'owner';

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-canvas text-ink">
      <Sidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
        onNewChat={handleNewChat}
        onRenameConversation={handleRename}
        onDeleteConversation={handleDelete}
        systemStatus={systemStatus}
        onRefreshHealth={handleRefreshHealth}
        isCollapsed={isSidebarCollapsed}
        setIsCollapsed={setIsSidebarCollapsed}
        currentUser={currentUser}
        onOpenAuth={() => setIsAuthModalOpen(true)}
        onOpenSettings={() => setIsSettingsModalOpen(true)}
        onLogout={handleLogout}
        onOpenDocuments={() => setIsDocumentsModalOpen(true)}
        onOpenMemory={() => setIsMemoryModalOpen(true)}
        onOpenResearch={() => setIsResearchModalOpen(true)}
        onOpenAgents={() => setIsAgentModalOpen(true)}
        onOpenAdmin={isOwner ? () => navigate('/admin') : undefined}
        theme={theme}
        onToggleTheme={handleToggleTheme}
      />

      <main className="flex-1 flex flex-col h-full overflow-hidden bg-canvas">
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 && !isStreaming ? (
            <WelcomeScreen onSelectPrompt={(p) => handleSend(p)} selectedModel={selectedModel} />
          ) : (
            <div className="max-w-3xl mx-auto py-6">
              {messages.map((msg, idx) => (
                <ChatMessage
                  key={msg.id}
                  message={msg}
                  onRegenerate={
                    msg.role === 'assistant' && idx === messages.length - 1 ? handleRegenerateLast : undefined
                  }
                />
              ))}

              {isStreaming && (
                <ChatMessage
                  message={{
                    id: 'streaming-assistant',
                    conversation_id: activeConversationId || '',
                    role: 'assistant',
                    content: streamingContent || 'Thinking...',
                    model: selectedModel,
                    tool_calls: streamingTools,
                    citations: streamingCitations,
                    charts: streamingCharts,
                    created_at: new Date().toISOString(),
                  }}
                  isStreaming={true}
                  streamingStatus={streamingStatus}
                />
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <div className="bg-canvas/90 backdrop-blur-sm">
          <Composer
            input={input}
            setInput={setInput}
            onSend={(text, images, opts) => handleSend(text, images, opts)}
            onStop={handleStopGeneration}
            isStreaming={isStreaming}
            selectedModel={selectedModel}
            models={models}
            onSelectModel={setSelectedModel}
            allowModelSwitching={allowSwitching}
            canManageModels={isOwner || allowSwitching}
            onOpenModelManagement={() => setIsModelModalOpen(true)}
            cloudAvailable={Boolean(publicIntelligence?.cloud_inference_enabled)}
          />
        </div>
      </main>

      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onSuccess={handleAuthSuccess}
      />

      <SettingsModal
        isOpen={isSettingsModalOpen}
        onClose={() => setIsSettingsModalOpen(false)}
        settings={userSettings}
        onUpdateSettings={(newSettings) => {
          setUserSettings(newSettings);
          if (newSettings.theme === 'light' || newSettings.theme === 'dark') {
            setTheme(newSettings.theme);
          }
          if (allowSwitching && newSettings.default_model) {
            setSelectedModel(newSettings.default_model);
          }
        }}
        models={models}
        allowModelSwitching={allowSwitching}
        serverPinnedModel={publicIntelligence?.active_model || selectedModel}
      />

      <ModelManagementModal
        isOpen={isModelModalOpen}
        onClose={() => setIsModelModalOpen(false)}
        models={models}
        providerHealths={systemStatus?.providers || []}
        onRefresh={handleRefreshHealth}
        isOwner={isOwner}
      />

      <DocumentsModal isOpen={isDocumentsModalOpen} onClose={() => setIsDocumentsModalOpen(false)} />
      <MemoryModal isOpen={isMemoryModalOpen} onClose={() => setIsMemoryModalOpen(false)} />
      <ResearchModal isOpen={isResearchModalOpen} onClose={() => setIsResearchModalOpen(false)} />
      <AgentModal isOpen={isAgentModalOpen} onClose={() => setIsAgentModalOpen(false)} />
    </div>
  );
};

export default App;
