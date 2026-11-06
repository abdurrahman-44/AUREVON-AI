import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Copy, Check, User, Sparkles } from 'lucide-react';
import { Message } from '../../types';

interface ChatMessageProps {
  message: Message;
  isStreaming?: boolean;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, isStreaming = false }) => {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={`group relative flex gap-4 px-4 py-5 md:px-8 transition-colors ${
        isUser ? 'bg-transparent' : 'bg-charcoal-900/40 border-y border-charcoal-800/40'
      }`}
    >
      {/* Avatar */}
      <div className="flex-shrink-0 pt-0.5">
        {isUser ? (
          <div className="w-8 h-8 rounded-lg bg-charcoal-800 border border-charcoal-700 flex items-center justify-center text-charcoal-300">
            <User size={16} />
          </div>
        ) : (
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-600 to-brand-700 border border-brand-500/50 flex items-center justify-center text-white shadow-sm shadow-brand-500/20">
            <Sparkles size={16} />
          </div>
        )}
      </div>

      {/* Message Body */}
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold tracking-wide uppercase text-charcoal-400">
              {isUser ? 'You' : 'AUREVON AI'}
            </span>
            {message.model && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-charcoal-800 text-charcoal-400 border border-charcoal-700/60 font-mono">
                {message.model}
              </span>
            )}
          </div>

          {/* Action buttons */}
          <div className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
            <button
              onClick={() => copyToClipboard(message.content)}
              className="p-1 rounded text-charcoal-400 hover:text-charcoal-200 hover:bg-charcoal-800 transition-colors"
              title="Copy message"
            >
              {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="prose-aurevon text-sm sm:text-base break-words">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ node, className, children, ...props }: any) {
                const match = /language-(\w+)/.exec(className || '');
                const isInline = !match && !String(children).includes('\n');
                
                if (isInline) {
                  return (
                    <code className="bg-charcoal-800 px-1.5 py-0.5 rounded text-brand-300 font-mono text-xs" {...props}>
                      {children}
                    </code>
                  );
                }

                const codeString = String(children).replace(/\n$/, '');
                return (
                  <div className="relative group/code my-3 rounded-lg overflow-hidden border border-charcoal-700/60 bg-charcoal-950">
                    <div className="flex items-center justify-between px-3 py-1.5 bg-charcoal-900 border-b border-charcoal-800 text-xs text-charcoal-400 font-mono">
                      <span>{match ? match[1] : 'code'}</span>
                      <button
                        onClick={() => copyToClipboard(codeString)}
                        className="flex items-center gap-1 hover:text-charcoal-200 transition-colors"
                      >
                        <Copy size={12} />
                        <span>Copy</span>
                      </button>
                    </div>
                    <pre className="p-3 text-xs sm:text-sm overflow-x-auto text-charcoal-200 font-mono">
                      <code>{children}</code>
                    </pre>
                  </div>
                );
              },
            }}
          >
            {message.content}
          </ReactMarkdown>
          {isStreaming && (
            <span className="inline-block w-2 h-4 ml-1 bg-brand-500 animate-pulse align-middle" />
          )}
        </div>
      </div>
    </div>
  );
};
