import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Check, Copy } from 'lucide-react';
import { Message } from '../../types';

interface ChatMessageProps {
  message: Message;
  isStreaming?: boolean;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, isStreaming = false }) => {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  if (isUser) {
    return (
      <div className="px-4 sm:px-6 py-3 flex justify-end">
        <div className="max-w-[82%] sm:max-w-[75%] rounded-2xl rounded-br-md border border-line bg-elevated px-4 py-3 text-sm sm:text-[15px] text-ink leading-relaxed whitespace-pre-wrap break-words">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="px-4 sm:px-6 py-4 group">
      <div className="flex items-start gap-3.5 max-w-3xl mx-auto">
        <div className="w-7 h-7 rounded-lg border border-line bg-surface flex items-center justify-center text-xs font-semibold text-ink shrink-0 mt-0.5">
          A
        </div>

        <div className="flex-1 min-w-0 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-ink">AUREVON</span>
              {message.model && (
                <span className="text-[11px] font-mono text-ink-muted">{message.model}</span>
              )}
              {isStreaming && (
                <span className="text-[11px] text-accent animate-pulse-subtle">Generating...</span>
              )}
            </div>

            {!isStreaming && message.content && (
              <button
                type="button"
                onClick={handleCopy}
                className="opacity-0 group-hover:opacity-100 inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] text-ink-muted hover:text-ink hover:bg-elevated transition-all"
                title="Copy response"
              >
                {copied ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
            )}
          </div>

          <div className="prose-aurevon break-words">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ node, inline, className, children, ...props }: any) {
                  return !inline ? (
                    <pre className="relative">
                      <code className={className} {...props}>
                        {children}
                      </code>
                    </pre>
                  ) : (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        </div>
      </div>
    </div>
  );
};
