import React from 'react';
import { Terminal, Shield, Sparkles, BookOpen, Layers, Cpu } from 'lucide-react';

interface WelcomeScreenProps {
  onSelectPrompt: (prompt: string) => void;
  selectedModel: string;
}

export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({ onSelectPrompt, selectedModel }) => {
  const suggestions = [
    {
      icon: Terminal,
      title: 'Architecture Blueprint',
      prompt: 'Design a modular, production-ready micro-agent architecture with Python and FastAPI.',
    },
    {
      icon: Shield,
      title: 'Security Code Audit',
      prompt: 'Review secure authentication strategies comparing JWT, HTTP-only cookies, and session tokens.',
    },
    {
      icon: Layers,
      title: 'Database Schema Design',
      prompt: 'Design an indexed PostgreSQL schema for conversational history, semantic memories, and document chunks.',
    },
    {
      icon: Cpu,
      title: 'Local AI Optimization',
      prompt: 'Explain how quantization (GGUF, Q4_K_M) enables fast LLM inference on modern CPU hardware.',
    },
  ];

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 md:p-12 text-center max-w-3xl mx-auto select-none">
      {/* Brand Hero */}
      <div className="w-16 h-16 rounded-2xl bg-charcoal-900 border border-charcoal-700/80 p-3 shadow-xl shadow-brand-500/10 mb-6 flex items-center justify-center relative group">
        <div className="absolute inset-0 bg-brand-500/20 rounded-2xl blur-xl group-hover:bg-brand-500/30 transition-all" />
        <img src="/logo.svg" alt="AUREVON AI" className="w-full h-full relative z-10" />
      </div>

      <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white mb-2">
        AUREVON AI
      </h1>
      <p className="text-sm sm:text-base text-charcoal-400 max-w-lg mb-8 leading-relaxed">
        Independent, multimodal, model-independent AI assistant platform. Local-first intelligence with complete privacy control.
      </p>

      {/* Capabilities Badges */}
      <div className="flex flex-wrap items-center justify-center gap-2 mb-10">
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-charcoal-900 border border-charcoal-800 text-charcoal-300">
          <Sparkles size={12} className="text-brand-400" />
          Active Model: <span className="text-white font-mono">{selectedModel}</span>
        </span>
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-charcoal-900 border border-charcoal-800 text-charcoal-300">
          <Shield size={12} className="text-emerald-400" />
          Local Execution
        </span>
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-charcoal-900 border border-charcoal-800 text-charcoal-300">
          <BookOpen size={12} className="text-sky-400" />
          Context Retention
        </span>
      </div>

      {/* Suggested Prompts Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full text-left">
        {suggestions.map((item, idx) => {
          const IconComponent = item.icon;
          return (
            <button
              key={idx}
              onClick={() => onSelectPrompt(item.prompt)}
              className="p-4 rounded-xl bg-charcoal-900/60 hover:bg-charcoal-900 border border-charcoal-800/80 hover:border-charcoal-700 transition-all text-left group flex flex-col justify-between"
            >
              <div className="flex items-center gap-2 mb-2 text-charcoal-200 group-hover:text-white transition-colors">
                <div className="p-1.5 rounded-lg bg-charcoal-800 text-brand-400 group-hover:bg-brand-500/20 transition-colors">
                  <IconComponent size={15} />
                </div>
                <span className="text-xs font-semibold uppercase tracking-wider">{item.title}</span>
              </div>
              <p className="text-xs text-charcoal-400 group-hover:text-charcoal-300 line-clamp-2 leading-relaxed">
                "{item.prompt}"
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
};
