import React, { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { AlertCircle, Bot, CheckCircle2, Clock, Play, Wrench, X } from 'lucide-react';
import { fetchAgentRuns, fetchAgentTools, runAgentTask } from '../../services/api';

interface AgentModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AgentModal: React.FC<AgentModalProps> = ({ isOpen, onClose }) => {
  const [tools, setTools] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [task, setTask] = useState('');
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentRun, setCurrentRun] = useState<any | null>(null);
  const [activeTab, setActiveTab] = useState<'run' | 'tools' | 'history'>('run');

  useEffect(() => {
    if (isOpen) {
      loadData();
    }
  }, [isOpen]);

  const loadData = async () => {
    try {
      const [toolsData, runsData] = await Promise.all([
        fetchAgentTools().catch(() => []),
        fetchAgentRuns().catch(() => []),
      ]);
      setTools(toolsData);
      setRuns(runsData);
    } catch (e) {
      console.error('Failed to load agent data:', e);
    }
  };

  if (!isOpen) return null;

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!task.trim()) return;
    setRunning(true);
    setError(null);
    setCurrentRun(null);
    try {
      const res = await runAgentTask(task.trim());
      setCurrentRun(res);
      await loadData();
    } catch (err: any) {
      setError(err.message || 'Agent run failed');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-3xl rounded-2xl border border-line bg-surface shadow-xl flex flex-col max-h-[88vh] overflow-hidden">
        <div className="px-6 py-4 border-b border-line flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Bot size={17} className="text-accent" />
            <div>
              <h2 className="text-sm font-semibold text-ink">Agent Task Runner</h2>
              <p className="text-[11px] text-ink-secondary">Controlled sandboxed tool execution and step trace logs</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-ink-muted hover:text-ink hover:bg-elevated">
            <X size={16} />
          </button>
        </div>

        <div className="px-6 border-b border-line flex items-center gap-2 text-xs">
          {[
            { id: 'run', label: 'Run Task' },
            { id: 'tools', label: `Tools (${tools.length})` },
            { id: 'history', label: `History (${runs.length})` },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`py-2.5 px-3 border-b-2 font-medium transition-colors ${
                activeTab === tab.id ? 'border-accent text-ink' : 'border-transparent text-ink-muted'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {error && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/25 text-xs text-rose-500 flex items-center gap-2">
              <AlertCircle size={14} />
              {error}
            </div>
          )}

          {activeTab === 'run' && (
            <div className="space-y-4">
              <form onSubmit={handleRun} className="space-y-3">
                <textarea
                  rows={3}
                  value={task}
                  onChange={(e) => setTask(e.target.value)}
                  placeholder="Describe a task (e.g., calculate (150 * 4) / 2 + 25, search documents, or analyze code)..."
                  className="w-full px-3.5 py-2.5 rounded-xl border border-line bg-canvas text-xs sm:text-sm text-ink focus:outline-none focus:border-accent"
                />
                <button
                  type="submit"
                  disabled={running || !task.trim()}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-xs font-medium"
                >
                  <Play size={13} />
                  {running ? 'Executing...' : 'Run Agent Task'}
                </button>
              </form>

              {currentRun && (
                <div className="space-y-4 pt-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="inline-flex items-center gap-1.5 font-medium text-emerald-500">
                      <CheckCircle2 size={14} />
                      Status: {currentRun.status}
                    </span>
                    <span className="font-mono text-[11px] text-ink-muted">{currentRun.id}</span>
                  </div>

                  {Array.isArray(currentRun.execution_log) && currentRun.execution_log.length > 0 && (
                    <div className="space-y-1.5">
                      <h4 className="text-xs font-medium text-ink-secondary">Execution Steps</h4>
                      {currentRun.execution_log.map((step: any, i: number) => (
                        <div key={i} className="rounded-xl border border-line bg-canvas px-3 py-2 text-xs font-mono">
                          <span className="text-accent">{step.step}</span>
                          <span className="text-ink-muted ml-2">
                            {typeof step.details === 'object' ? JSON.stringify(step.details) : String(step.details || '')}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  {currentRun.final_output && (
                    <div className="rounded-xl border border-line bg-canvas p-4 prose-aurevon">
                      <ReactMarkdown>{currentRun.final_output}</ReactMarkdown>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === 'tools' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {tools.map((t) => (
                <div key={t.name} className="rounded-xl border border-line bg-canvas p-4 space-y-1">
                  <div className="flex items-center gap-2 text-xs font-mono font-medium text-ink">
                    <Wrench size={13} className="text-accent" />
                    {t.name}
                  </div>
                  <p className="text-xs text-ink-secondary">{t.description}</p>
                </div>
              ))}
            </div>
          )}

          {activeTab === 'history' && (
            <div className="space-y-2.5">
              {runs.length === 0 ? (
                <p className="text-xs text-ink-muted">No agent runs recorded in this workspace.</p>
              ) : (
                runs.map((r) => (
                  <div key={r.id} className="rounded-xl border border-line bg-canvas p-3.5 text-xs space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-ink truncate">{r.task}</span>
                      <span className="inline-flex items-center gap-1 text-[11px] font-mono text-ink-muted shrink-0">
                        <Clock size={11} />
                        {r.status}
                      </span>
                    </div>
                    {r.final_output && (
                      <p className="text-ink-secondary line-clamp-2">{r.final_output}</p>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
