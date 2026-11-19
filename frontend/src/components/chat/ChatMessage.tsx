import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Calendar,
  Check,
  CloudSun,
  Coins,
  Copy,
  ExternalLink,
  FileText,
  Newspaper,
  RotateCcw,
  Terminal,
  Wrench,
} from 'lucide-react';
import { Message } from '../../types';

interface ChatMessageProps {
  message: Message;
  isStreaming?: boolean;
  streamingStatus?: string | null;
  onRegenerate?: () => void;
}

const getStatusLabel = (status: string | null): string => {
  switch (status) {
    case 'weather_fetching':
      return 'Checking live weather...';
    case 'news_fetching':
      return 'Searching recent news...';
    case 'currency_converting':
      return 'Calculating exchange rate...';
    case 'calculating':
      return 'Evaluating calculation...';
    case 'executing_code':
      return 'Running Python sandbox...';
    case 'researching':
      return 'Conducting research...';
    case 'retrieving':
      return 'Searching knowledge...';
    case 'tool_running':
      return 'Running verified tool...';
    default:
      return 'Generating...';
  }
};

const getToolIcon = (toolName: string) => {
  if (toolName === 'weather') return <CloudSun size={11} />;
  if (toolName === 'currency_converter') return <Coins size={11} />;
  if (toolName === 'news_search') return <Newspaper size={11} />;
  if (toolName === 'date_time') return <Calendar size={11} />;
  if (toolName === 'python_data_analysis') return <Terminal size={11} />;
  return <Wrench size={11} />;
};

const CodeBlock: React.FC<{ className?: string; children: React.ReactNode }> = ({ className, children }) => {
  const [copiedCode, setCopiedCode] = useState(false);
  const raw = String(children ?? '').replace(/\n$/, '');
  const langMatch = /language-([a-zA-Z0-9_+-]+)/.exec(className || '');
  const lang = langMatch ? langMatch[1] : 'code';

  const handleCopyCode = () => {
    navigator.clipboard.writeText(raw);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 1600);
  };

  return (
    <div className="my-3 rounded-xl border border-line bg-canvas overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-line bg-elevated/60 text-[11px] text-ink-muted">
        <span className="font-mono uppercase tracking-wider">{lang}</span>
        <button
          type="button"
          onClick={handleCopyCode}
          className="inline-flex items-center gap-1 hover:text-ink transition-colors"
        >
          {copiedCode ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
          <span>{copiedCode ? 'Copied' : 'Copy code'}</span>
        </button>
      </div>
      <pre className="p-3 overflow-x-auto text-xs leading-relaxed">
        <code className={className}>{children}</code>
      </pre>
    </div>
  );
};

export const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  isStreaming = false,
  streamingStatus = null,
  onRegenerate,
}) => {
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

  const safeCharts = (message.charts || []).filter(
    (svg) =>
      typeof svg === 'string' &&
      svg.trim().startsWith('<svg') &&
      !/<script/i.test(svg) &&
      !/on[a-z]+\s*=/i.test(svg)
  );

  return (
    <div className="px-4 sm:px-6 py-4 group">
      <div className="flex items-start gap-3.5 max-w-3xl mx-auto">
        <div className="w-7 h-7 rounded-lg border border-line bg-surface flex items-center justify-center text-xs font-semibold text-ink shrink-0 mt-0.5">
          A
        </div>

        <div className="flex-1 min-w-0 space-y-2.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-medium text-ink">AUREVON</span>
              {message.model && (
                <span className="text-[11px] font-mono text-ink-muted">{message.model}</span>
              )}
              {message.intent && (
                <span className="px-1.5 py-0.5 rounded bg-elevated border border-line text-[10px] font-mono text-ink-muted">
                  {message.intent}
                </span>
              )}
              {isStreaming && (
                <span className="text-[11px] text-accent animate-pulse-subtle">
                  {getStatusLabel(streamingStatus)}
                </span>
              )}
            </div>

            {!isStreaming && message.content && (
              <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1 transition-all">
                {onRegenerate && (
                  <button
                    type="button"
                    onClick={onRegenerate}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] text-ink-muted hover:text-ink hover:bg-elevated transition-all"
                    title="Regenerate response"
                  >
                    <RotateCcw size={12} />
                    <span>Regenerate</span>
                  </button>
                )}
                <button
                  type="button"
                  onClick={handleCopy}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] text-ink-muted hover:text-ink hover:bg-elevated transition-all"
                  title="Copy response"
                >
                  {copied ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
            )}
          </div>

          {/* Tool Activity Pills */}
          {message.tool_calls && message.tool_calls.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {message.tool_calls.map((tc, idx) => {
                const ok = tc.ok !== false && tc.status === 'success';
                return (
                  <div
                    key={`${tc.tool}-${idx}`}
                    className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-lg border text-[11px] font-mono ${
                      ok
                        ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-500'
                        : 'border-amber-500/25 bg-amber-500/10 text-amber-500'
                    }`}
                  >
                    {getToolIcon(tc.tool)}
                    <span>{tc.tool}</span>
                    {typeof tc.duration_ms === 'number' && (
                      <span className="opacity-75">{tc.duration_ms}ms</span>
                    )}
                    {tc.formatted && <span className="text-ink">= {tc.formatted}</span>}
                    {tc.result !== undefined && <span className="text-ink">= {String(tc.result)}</span>}
                  </div>
                );
              })}
            </div>
          )}

          <div className="prose-aurevon break-words">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ node, inline, className, children, ...props }: any) {
                  return !inline ? (
                    <CodeBlock className={className}>{children}</CodeBlock>
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

          {/* Sandboxed SVG Charts produced by Python Data Analysis Tool */}
          {safeCharts.length > 0 && (
            <div className="space-y-2 pt-1">
              {safeCharts.map((svg, idx) => (
                <div
                  key={idx}
                  className="rounded-xl border border-line bg-canvas p-2 overflow-x-auto"
                  dangerouslySetInnerHTML={{ __html: svg }}
                />
              ))}
            </div>
          )}

          {/* Grounded Citations */}
          {message.citations && message.citations.length > 0 && (
            <div className="pt-2 border-t border-line/60 space-y-1.5">
              <div className="text-[11px] font-medium text-ink-muted uppercase tracking-wider">
                Sources & Citations ({message.citations.length})
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                {message.citations.map((cit, idx) => (
                  <div
                    key={idx}
                    className="rounded-lg border border-line bg-surface px-2.5 py-2 text-xs space-y-0.5"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="inline-flex items-center gap-1 font-medium text-ink truncate">
                        <FileText size={11} className="text-accent shrink-0" />
                        {cit.source_type === 'web'
                          ? cit.title || cit.url
                          : `${cit.filename || 'Document'}${cit.page_number ? ` · Sec ${cit.page_number}` : ''}`}
                      </span>
                      {typeof cit.similarity === 'number' && (
                        <span className="text-[10px] font-mono text-ink-muted shrink-0">
                          {Math.round(cit.similarity * 100)}%
                        </span>
                      )}
                      {cit.source_type === 'web' && cit.url && (
                        <a
                          href={cit.url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-accent hover:underline shrink-0"
                          title="Open source"
                        >
                          <ExternalLink size={11} />
                        </a>
                      )}
                    </div>
                    {cit.snippet && (
                      <p className="text-[11px] text-ink-muted line-clamp-2">{cit.snippet}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
