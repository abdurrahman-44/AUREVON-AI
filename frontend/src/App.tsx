import React, { useState, useEffect, useRef } from 'react';
import { Sidebar } from './components/sidebar/Sidebar';
import { ChatMessage } from './components/chat/ChatMessage';
import { WelcomeScreen } from './components/chat/WelcomeScreen';
import { Composer } from './components/composer/Composer';
import {
  fetchConversations,
  fetchConversation,
  updateConversationTitle,
  deleteConversation,
  fetchModels,
  fetchSystemHealth,
  streamChat,
} from './services/api';
import { Conversation, Message, ModelInfo, SystemStatus } from './types';

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

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Initial load: Fetch conversations, models, and health status
  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
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
      if (defaultM) setSelectedModel(defaultM.id);
    } catch (err) {
      console.error('Error loading initial data:', err);
    }
  };

  const handleRefreshHealth = async () => {
    try {
      const [health, modelList] = await Promise.all([
        fetchSystemHealth(),
        fetchModels(),
      ]);
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
    </div>
  );
};

export default App;
