import React, { useState } from 'react';
import { X, Globe, Search, ExternalLink, Copy, Check, Sparkles, BookOpen, AlertCircle } from 'lucide-react';
import { executeResearch } from '../../services/api';

interface ResearchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ResearchModal: React.FC<ResearchModalProps> = ({ isOpen, onClose }) => {
  const [query, setQuery] = useState('');
  const [maxSources, setMaxSources] = useState(4);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [researchData, setResearchData] = useState<any | null>(null);
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setResearchData(null);
    try {
      const data = await executeResearch(query.trim(), maxSources);
      setResearchData(data);
    } catch (err: any) {
      setError(err.message || 'Web research failed. Please check network or query.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopyReport = () => {
    if (!researchData) return;
    const text = `# Research Report: ${researchData.query}\n\n${researchData.synthesis}\n\n## Sources\n` +
      researchData.sources.map((s: any, idx: number) => `[${idx + 1}] ${s.title}: ${s.url}`).join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-3xl bg-charcoal-900 border border-charcoal-700/80 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-charcoal-800">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-teal-500/10 text-teal-400">
              <Globe className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Autonomous Web Research</h2>
              <p className="text-xs text-charcoal-400">Live internet search, content aggregation & grounded source synthesis</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-charcoal-400 hover:text-white rounded-lg hover:bg-charcoal-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 custom-scrollbar">
          {/* Search Form */}
          <form onSubmit={handleSearch} className="space-y-3">
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="w-4 h-4 absolute left-3.5 top-3 text-charcoal-400" />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Enter research topic (e.g., Latest breakthroughs in solid state batteries)..."
                  className="w-full pl-10 pr-4 py-2.5 bg-charcoal-800 border border-charcoal-700 rounded-xl text-sm text-charcoal-100 placeholder-charcoal-500 focus:outline-none focus:border-teal-500"
                />
              </div>
              <div className="flex items-center bg-charcoal-800 border border-charcoal-700 rounded-xl px-3">
                <span className="text-xs text-charcoal-400 mr-2">Sources:</span>
                <select
                  value={maxSources}
                  onChange={(e) => setMaxSources(Number(e.target.value))}
                  className="bg-transparent text-xs text-charcoal-200 focus:outline-none"
                >
                  <option value={2} className="bg-charcoal-800">2</option>
                  <option value={4} className="bg-charcoal-800">4</option>
                  <option value={6} className="bg-charcoal-800">6</option>
                  <option value={8} className="bg-charcoal-800">8</option>
                </select>
              </div>
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="px-5 py-2.5 bg-teal-500 hover:bg-teal-600 disabled:opacity-50 text-white font-medium text-sm rounded-xl flex items-center space-x-2 transition shrink-0"
              >
                <Sparkles className="w-4 h-4" />
                <span>{loading ? 'Researching...' : 'Synthesize'}</span>
              </button>
            </div>
          </form>

          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {loading && (
            <div className="flex flex-col items-center justify-center py-12 space-y-3">
              <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-xs text-charcoal-300">Searching web sources and generating verified report...</p>
            </div>
          )}

          {researchData && (
            <div className="space-y-6">
              {/* Synthesis Report Card */}
              <div className="p-5 bg-charcoal-800/60 border border-charcoal-700/60 rounded-xl space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-charcoal-700/60">
                  <div className="flex items-center space-x-2 text-teal-400 text-xs font-semibold uppercase tracking-wider">
                    <BookOpen className="w-4 h-4" />
                    <span>Synthesized Intelligence</span>
                  </div>
                  <button
                    onClick={handleCopyReport}
                    className="p-1.5 text-charcoal-400 hover:text-white rounded-lg hover:bg-charcoal-700 transition flex items-center gap-1 text-xs"
                  >
                    {copied ? <Check className="w-3.5 h-3.5 text-teal-400" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copied ? 'Copied' : 'Copy Report'}</span>
                  </button>
                </div>
                <div className="text-sm text-charcoal-100 whitespace-pre-wrap leading-relaxed">
                  {researchData.synthesis}
                </div>
              </div>

              {/* Source Citations */}
              <div className="space-y-3">
                <div className="text-xs font-semibold uppercase tracking-wider text-charcoal-400">
                  Grounding Sources & Citations ({researchData.sources?.length || 0})
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {researchData.sources?.map((source: any, idx: number) => (
                    <a
                      key={idx}
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-3.5 bg-charcoal-800/40 hover:bg-charcoal-800 border border-charcoal-700/50 hover:border-teal-500/50 rounded-xl transition group flex flex-col justify-between"
                    >
                      <div className="space-y-1">
                        <div className="flex items-start justify-between gap-2">
                          <h4 className="text-xs font-semibold text-charcoal-200 group-hover:text-teal-400 line-clamp-1">
                            [{idx + 1}] {source.title}
                          </h4>
                          <ExternalLink className="w-3.5 h-3.5 text-charcoal-500 group-hover:text-teal-400 shrink-0" />
                        </div>
                        <p className="text-[11px] text-charcoal-400 line-clamp-2 leading-relaxed">
                          {source.snippet}
                        </p>
                      </div>
                      <span className="text-[10px] text-charcoal-500 truncate pt-2">
                        {source.url}
                      </span>
                    </a>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
