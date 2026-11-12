import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { AlertCircle, BookOpen, Check, Copy, ExternalLink, Globe, Search, X } from 'lucide-react';
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
  const [researchData, setResearchData] = useState<{
    query: string;
    summary: string;
    citations: { title: string; snippet: string; url: string }[];
    source_count: number;
  } | null>(null);
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
      setError(err.message || 'Web research failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopyReport = () => {
    if (!researchData) return;
    const citationsText = (researchData.citations || [])
      .map((c, idx) => `[${idx + 1}] ${c.title}: ${c.url}`)
      .join('\n');
    const text = `# Research Report: ${researchData.query}\n\n${researchData.summary}\n\n## Citations\n${citationsText}`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-3xl rounded-2xl border border-line bg-surface shadow-xl flex flex-col max-h-[88vh] overflow-hidden">
        <div className="px-6 py-4 border-b border-line flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Globe size={17} className="text-accent" />
            <div>
              <h2 className="text-sm font-semibold text-ink">Web Research</h2>
              <p className="text-[11px] text-ink-secondary">Retrieve live search references with explicit source links</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-ink-muted hover:text-ink hover:bg-elevated">
            <X size={16} />
          </button>
        </div>

        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          <form onSubmit={handleSearch} className="flex flex-wrap sm:flex-nowrap gap-2">
            <div className="relative flex-1 min-w-[200px]">
              <Search size={14} className="absolute left-3.5 top-3 text-ink-muted" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search external references..."
                className="w-full pl-9 pr-3.5 py-2.5 rounded-xl border border-line bg-canvas text-xs sm:text-sm text-ink focus:outline-none focus:border-accent"
              />
            </div>
            <select
              value={maxSources}
              onChange={(e) => setMaxSources(Number(e.target.value))}
              className="px-3 py-2.5 rounded-xl border border-line bg-canvas text-xs text-ink"
            >
              <option value={2}>2 sources</option>
              <option value={4}>4 sources</option>
              <option value={6}>6 sources</option>
              <option value={8}>8 sources</option>
            </select>
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="px-5 py-2.5 rounded-xl bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-xs font-medium transition-colors"
            >
              {loading ? 'Searching...' : 'Research'}
            </button>
          </form>

          {error && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/25 text-xs text-rose-500 flex items-center gap-2">
              <AlertCircle size={14} />
              {error}
            </div>
          )}

          {researchData && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-secondary">
                  <BookOpen size={14} className="text-accent" />
                  {researchData.source_count} source{researchData.source_count === 1 ? '' : 's'} returned
                </span>
                <button
                  onClick={handleCopyReport}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-line text-xs text-ink-secondary hover:text-ink"
                >
                  {copied ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                  {copied ? 'Copied' : 'Copy Brief'}
                </button>
              </div>

              <div className="rounded-xl border border-line bg-canvas p-4 prose-aurevon">
                <ReactMarkdown>{researchData.summary}</ReactMarkdown>
              </div>

              {researchData.citations.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-xs font-medium text-ink-secondary">Source Citations</h4>
                  {researchData.citations.map((c, idx) => (
                    <a
                      key={idx}
                      href={c.url}
                      target="_blank"
                      rel="noreferrer"
                      className="block rounded-xl border border-line bg-canvas hover:border-line-strong p-3.5 transition-colors space-y-1"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-medium text-ink">{c.title}</span>
                        <ExternalLink size={12} className="text-ink-muted shrink-0" />
                      </div>
                      <p className="text-xs text-ink-secondary line-clamp-2">{c.snippet}</p>
                      <span className="block text-[11px] font-mono text-accent truncate">{c.url}</span>
                    </a>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
