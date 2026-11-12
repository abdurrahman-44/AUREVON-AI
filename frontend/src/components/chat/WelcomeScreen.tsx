import React from 'react';
import { BookOpen, Code2, Cpu, Lightbulb } from 'lucide-react';

interface WelcomeScreenProps {
  onSelectPrompt: (prompt: string) => void;
  selectedModel: string;
}

const STARTERS = [
  {
    icon: <Code2 size={15} />,
    title: 'Debug or explain code',
    prompt: 'Review an asynchronous Python service pattern and explain common concurrency pitfalls.',
  },
  {
    icon: <BookOpen size={15} />,
    title: 'Synthesize documents',
    prompt: 'Summarize the core themes from my uploaded knowledge base documents cleanly.',
  },
  {
    icon: <Lightbulb size={15} />,
    title: 'Reason step by step',
    prompt: 'Compare SQLite and PostgreSQL trade-offs for an evolving AI platform with transparent pros and cons.',
  },
  {
    icon: <Cpu size={15} />,
    title: 'Plan a technical system',
    prompt: 'Outline a clear, reliable architecture checklist before deploying a web API to production.',
  },
];

export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({ onSelectPrompt, selectedModel }) => {
  return (
    <div className="min-h-full flex flex-col items-center justify-center px-6 py-12">
      <div className="w-full max-w-2xl space-y-8">
        <div className="space-y-3 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-line bg-surface text-xs text-ink-secondary">
            <span className="w-1.5 h-1.5 rounded-full bg-accent" />
            <span className="font-mono">{selectedModel}</span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-ink">
            How can AUREVON help?
          </h1>
          <p className="text-sm text-ink-secondary max-w-lg mx-auto leading-relaxed">
            Calm, grounded reasoning across conversations, documents, memory, web search, and structured tools.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {STARTERS.map((s) => (
            <button
              key={s.title}
              type="button"
              onClick={() => onSelectPrompt(s.prompt)}
              className="text-left p-4 rounded-2xl border border-line bg-surface hover:bg-elevated/70 hover:border-line-strong transition-colors group"
            >
              <div className="flex items-center gap-2 text-xs font-medium text-ink mb-1.5">
                <span className="text-ink-muted group-hover:text-accent transition-colors">{s.icon}</span>
                <span>{s.title}</span>
              </div>
              <p className="text-xs text-ink-secondary leading-relaxed line-clamp-2">{s.prompt}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
