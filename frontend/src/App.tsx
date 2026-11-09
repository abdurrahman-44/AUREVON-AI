import React, { useState, useEffect, useRef } from 'react';
import { Sidebar } from './components/sidebar/Sidebar';
import { ChatMessage } from './components/chat/ChatMessage';
import { WelcomeScreen } from './components/chat/WelcomeScreen';
import { Composer } from './components/composer/Composer';
import { AuthModal } from './components/auth/AuthModal';
import { SettingsModal } from './components/settings/SettingsModal';
import {
  fetchConversations,
  fetchConversation,
  updateConversationTitle,
  deleteConversation,
  fetchModels,
  fetchSystemHealth,
  fetchMe,
  streamChat,
} from './services/api';
import { Conversation, Message, ModelInfo, SystemStatus, User, UserSettings } from './types';

export const App: React.FC = () => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('qwen2.5:3b');
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  // Phase 2: User Accounts & Settings State
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [userSettings, setUserSettings] = useState<UserSettings | null>(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Initial load
  useEffect(() => {
    loadInitialData();
  }, []);

  // Theme application
  useEffect(() => {
    const activeTheme = userSettings?.theme || 'dark';
    if (activeTheme === 'dark') {
      document.documentElement.classList.add('dark');
      document.documentElement.classList.remove('light');
    } else if (activeTheme === 'light') {
      document.documentElement.classList.add('light');
      document.documentElement.classList.remove('dark');
    } else {
      // System mode
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      document.documentElement.classList.toggle('dark', prefersDark);
    }
  }, [userSettings?.theme]);

  const loadInitialData = async () => {
    // 1. Try restoring user session if token exists
    const token = localStorage.getItem('aurevon_token');
    if (token) {
      try {
        const user = await fetchMe();
        setCurrentUser(user);
        if (user.settings) {
          setUserSettings(user.settings);
          if (user.settings.default_model) {
            setSelectedModel(user.settings.default_model);
          }
        }
      } catch (e) {
        console.warn('Session expired or invalid token:', e);
        localStorage.removeItem('aurevon_token');
      }
    }

    // 2. Fetch conversations, models, and health
    try {
      const [convs, modelList, health] = await Promise.all([
        fetchConversations(),
        fetchModels(),
        fetchSystemHealth(),
      ]);

      setConversations(convs);
      setModels(modelList);
      setSystemStatus(health);

      const defaultM = modelList.find((m) => m.is_default) || modelList[0];
      if (defaultM && !userSettings?.default_model) {
        setSelectedModel(defaultM.id);
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
      if (user.settings.default_model) {
        setSelectedModel(user.settings.default_model);
      }
    }
    // Reload user-scoped conversations
    try {
      const convs = await fetchConversations();
      setConversations(convs);
    } catch (e) {
      console.error('Failed to reload conversations:', e);
    }
  };

  const handleLogout = async () => {
    localStorage.removeItem('aurevon_token');
    setCurrentUser(null);
    setUserSettings(null);
    handleNewChat();
    // Reload guest/unassigned conversations
    try {
      const convs = await fetchConversations();
      setConversations(convs);
    } catch (e) {
      console.error('Failed to reload conversations:', e);
    }
  };

  const handleRefreshHealth = async () => {
    try {
      const [health, modelList] = await Promise.all([fetchSystemHealth(), fetchModels()]);
      setSystemStatus(health);
      setModels(modelList);
    } catch (e) {
      console.error('Failed to refresh health:', e);
    }
  };

  // Switch active conversation
  const handleSelectConversation = async (id: string) => {
    if (isStreaming) {
      handleStopGeneration();
    }
    setActiveConversationId(id);
    try {
      const detail = await fetchConversation(id);
      setMessages(detail.messages || []);
    } catch (err) {
      console.error('Error fetching conversation detail:', err);
    }
  };

  // Start new chat
  const handleNewChat = () => {
    if (isStreaming) {
      handleStopGeneration();
    }
    setActiveConversationId(null);
    setMessages([]);
    setInput('');
    setStreamingContent('');
  };

  // Rename conversation
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

  // Delete conversation
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

  // Auto scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent]);

  // Send message and stream AI response
  const handleSend = async (customPrompt?: string) => {
    const promptToSend = (customPrompt || input).trim();
    if (!promptToSend || isStreaming) return;

    setInput('');
    const tempUserMessage: Message = {
      id: `temp-${Date.now()}`,
      conversation_id: activeConversationId || '',
      role: 'user',
      content: promptToSend,
      model: selectedModel,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, tempUserMessage]);
    setIsStreaming(true);
    setStreamingContent('');

    const controller = new AbortController();
    abortControllerRef.current = controller;

    let currentConversationId = activeConversationId;
    let accumulated = '';

    try {
      await streamChat({
        conversationId: activeConversationId || undefined,
        message: promptToSend,
        model: selectedModel,
        abortSignal: controller.signal,
        onInit: (data) => {
          if (!currentConversationId && data.conversation_id) {
            currentConversationId = data.conversation_id;
            setActiveConversationId(data.conversation_id);
          }
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
            model: selectedModel,
            created_at: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, finalAssistantMsg]);
          setStreamingContent('');

          // Refresh conversation list to get updated titles and ordering
          const updatedConvs = await fetchConversations();
          setConversations(updatedConvs);
        },
        onError: (err) => {
          console.error('Stream failed:', err);
          setIsStreaming(false);
          setStreamingContent('');
        },
      });
    } catch (err) {
      console.error('Error during send:', err);
      setIsStreaming(false);
      setStreamingContent('');
    }
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (streamingContent) {
      const truncatedMsg: Message = {
        id: `asst-stop-${Date.now()}`,
        conversation_id: activeConversationId || '',
        role: 'assistant',
        content: streamingContent + ' *(Generation stopped by user)*',
        model: selectedModel,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, truncatedMsg]);
    }
    setIsStreaming(false);
    setStreamingContent('');
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-charcoal-950 text-charcoal-100">
      {/* Sidebar */}
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
      />

      {/* Main Chat Viewport */}
      <main className="flex-1 flex flex-col h-full overflow-hidden relative">
        {/* Messages Scroll Area */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 && !isStreaming ? (
            <WelcomeScreen
              onSelectPrompt={(p) => handleSend(p)}
              selectedModel={selectedModel}
            />
          ) : (
            <div className="max-w-4xl mx-auto py-4">
              {messages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
              ))}

              {/* In-flight streaming response chunk */}
              {isStreaming && (
                <ChatMessage
                  message={{
                    id: 'streaming-assistant',
                    conversation_id: activeConversationId || '',
                    role: 'assistant',
                    content: streamingContent || 'Thinking...',
                    model: selectedModel,
                    created_at: new Date().toISOString(),
                  }}
                  isStreaming={true}
                />
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Composer Bar */}
        <div className="border-t border-charcoal-800/80 bg-charcoal-950/80 backdrop-blur-md">
          <Composer
            input={input}
            setInput={setInput}
            onSend={() => handleSend()}
            onStop={handleStopGeneration}
            isStreaming={isStreaming}
            selectedModel={selectedModel}
            models={models}
            onSelectModel={setSelectedModel}
          />
        </div>
      </main>

      {/* Phase 2: Modals */}
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
          if (newSettings.default_model) {
            setSelectedModel(newSettings.default_model);
          }
        }}
        models={models}
      />
    </div>
  );
};

export default App;
