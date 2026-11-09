import React, { useState, useEffect } from 'react';
import { X, Bot, Play, CheckCircle2, Clock, Terminal, ChevronRight, AlertCircle, Wrench, RefreshCw } from 'lucide-react';
import { fetchAgentTools, runAgentTask, fetchAgentRuns } from '../../services/api';

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
  const [currentRunResult, setCurrentRunResult] = useState<any | null>(null);
  const [activeTab, setActiveTab] = useState<'run' | 'history' | 'tools'>('run');

  useEffect(() => {
    if (isOpen) {
      loadToolsAndRuns();
    }
  }, [isOpen]);

  const loadToolsAndRuns = async () => {
    try {
      const [toolsData, runsData] = await Promise.all([
        fetchAgentTools().catch(() => []),
        fetchAgentRuns().catch(() => [])
      ]);
      setTools(toolsData);
      setRuns(runsData);
    } catch (e) {
      console.error('Failed to load agent info:', e);
    }
  };

  if (!isOpen) return null;

  const handleRunAgent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!task.trim()) return;

    setRunning(true);
    setError(null);
    setCurrentRunResult(null);

    try {
      const result = await runAgentTask(task.trim());
      setCurrentRunResult(result);
      await loadToolsAndRuns();
    } catch (err: any) {
      setError(err.message || 'Agent execution failed');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-4xl bg-charcoal-900 border border-charcoal-700/80 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-charcoal-800">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-teal-500/10 text-teal-400">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Autonomous Agent Runner</h2>
              <p className="text-xs text-charcoal-400">Multi-step reasoning, tool invocation, code analysis & grounded task synthesis</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-charcoal-400 hover:text-white rounded-lg hover:bg-charcoal-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center px-6 border-b border-charcoal-800 bg-charcoal-950/40 text-xs">
          <button
            onClick={() => setActiveTab('run')}
            className={`py-3 px-4 font-medium border-b-2 transition ${
              activeTab === 'run'
                ? 'border-teal-400 text-teal-400'
                : 'border-transparent text-charcoal-400 hover:text-charcoal-200'
            }`}
          >
            Task Execution
          </button>
          <button
            onClick={() => setActiveTab('tools')}
            className={`py-3 px-4 font-medium border-b-2 transition flex items-center gap-1.5 ${
              activeTab === 'tools'
                ? 'border-teal-400 text-teal-400'
                : 'border-transparent text-charcoal-400 hover:text-charcoal-200'
            }`}
          >
            <Wrench className="w-3.5 h-3.5" />
            <span>Registered Tools ({tools.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`py-3 px-4 font-medium border-b-2 transition flex items-center gap-1.5 ${
              activeTab === 'history'
                ? 'border-teal-400 text-teal-400'
                : 'border-transparent text-charcoal-400 hover:text-charcoal-200'
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            <span>Execution Audit Log ({runs.length})</span>
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 custom-scrollbar">
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {activeTab === 'run' && (
            <div className="space-y-6">
              {/* Task Dispatch Box */}
              <form onSubmit={handleRunAgent} className="p-4 bg-charcoal-800/60 border border-charcoal-700/60 rounded-xl space-y-3">
                <div className="text-xs font-semibold uppercase tracking-wider text-charcoal-300">
                  Dispatch Autonomous Agent Task
                </div>
                <textarea
                  value={task}
                  onChange={(e) => setTask(e.target.value)}
                  placeholder="e.g., Calculate (150 * 4) / 2 + 25 and check if python code 'def hello(): pass' is valid"
                  rows={2}
                  className="w-full bg-charcoal-900 border border-charcoal-700 rounded-lg p-3 text-sm text-charcoal-100 placeholder-charcoal-500 focus:outline-none focus:border-teal-500"
                />
                <div className="flex items-center justify-between pt-1">
                  <div className="flex items-center space-x-2 text-xs text-charcoal-400">
                    <span>Available tools:</span>
                    <span className="text-teal-400 font-mono text-[11px]">
                      {tools.map(t => t.name).join(', ') || 'calculator, code_analyzer, search, doc_search'}
                    </span>
                  </div>
                  <button
                    type="submit"
                    disabled={running || !task.trim()}
                    className="px-5 py-2 bg-teal-500 hover:bg-teal-600 disabled:opacity-50 text-white font-medium text-xs rounded-lg flex items-center space-x-2 transition"
                  >
                    <Play className="w-3.5 h-3.5 fill-current" />
                    <span>{running ? 'Agent Reasoning...' : 'Execute Task'}</span>
                  </button>
                </div>
              </form>

              {running && (
                <div className="flex flex-col items-center justify-center py-8 space-y-3">
                  <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
                  <p className="text-xs text-charcoal-300">
                    Agent evaluating plan, inspecting tools and executing multi-step reasoning...
                  </p>
                </div>
              )}

              {/* Execution Steps & Output */}
              {currentRunResult && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-teal-400 flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4 text-teal-400" />
                      <span>Execution Result: {currentRunResult.status}</span>
                    </h3>
                    <span className="text-xs text-charcoal-400">
                      ID: <span className="font-mono text-charcoal-300">{currentRunResult.id}</span>
                    </span>
                  </div>

                  {/* Step Timeline */}
                  <div className="space-y-2">
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-charcoal-400">
                      Step Trace Log ({currentRunResult.steps?.length || 0} steps)
                    </div>
                    {currentRunResult.steps?.map((step: any, idx: number) => (
                      <div
                        key={idx}
                        className="p-3 bg-charcoal-800/40 border border-charcoal-700/60 rounded-xl space-y-2 text-xs"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-2">
                            <span className="w-5 h-5 rounded-full bg-teal-500/20 text-teal-400 flex items-center justify-center text-[10px] font-bold">
                              {step.step || idx + 1}
                            </span>
                            <span className="font-semibold text-charcoal-200">
                              Tool: <span className="text-teal-300 font-mono">{step.tool}</span>
                            </span>
                          </div>
                          <span className="text-[10px] text-charcoal-400">
                            {step.status || 'completed'}
                          </span>
                        </div>
                        {step.input && (
                          <div className="bg-charcoal-900/80 p-2 rounded text-[11px] font-mono text-charcoal-300 break-all">
                            <span className="text-charcoal-500">Input:</span> {JSON.stringify(step.input)}
                          </div>
                        )}
                        {step.output && (
                          <div className="bg-charcoal-900/80 p-2 rounded text-[11px] font-mono text-teal-400 break-all">
                            <span className="text-charcoal-500">Output:</span> {JSON.stringify(step.output)}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Final Output */}
                  <div className="p-4 bg-teal-950/20 border border-teal-500/30 rounded-xl space-y-1.5">
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-teal-400">
                      Final Synthesized Agent Output
                    </div>
                    <div className="text-sm text-charcoal-100 whitespace-pre-wrap leading-relaxed">
                      {currentRunResult.final_output || 'Task completed successfully.'}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'tools' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {tools.map((t, idx) => (
                <div key={idx} className="p-4 bg-charcoal-800/50 border border-charcoal-700/60 rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Terminal className="w-4 h-4 text-teal-400" />
                      <span className="font-mono text-xs font-semibold text-white">{t.name}</span>
                    </div>
                    <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded bg-teal-500/10 text-teal-400 border border-teal-500/20">
                      Sandboxed
                    </span>
                  </div>
                  <p className="text-xs text-charcoal-300 leading-relaxed">{t.description}</p>
                </div>
              ))}
            </div>
          )}

          {activeTab === 'history' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-charcoal-400">Past Agent Executions</span>
                <button
                  onClick={loadToolsAndRuns}
                  className="text-xs text-teal-400 hover:text-teal-300 flex items-center gap-1"
                >
                  <RefreshCw className="w-3 h-3" />
                  <span>Refresh</span>
                </button>
              </div>
              {runs.length === 0 ? (
                <div className="text-center py-8 text-charcoal-400 text-xs">
                  No previous agent runs recorded.
                </div>
              ) : (
                runs.map((r) => (
                  <div key={r.id} className="p-3 bg-charcoal-800/40 border border-charcoal-700/50 rounded-xl text-xs space-y-1.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-white truncate max-w-md">{r.task}</span>
                      </div>
                      <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-semibold ${
                        r.status === 'completed'
                          ? 'bg-teal-500/10 text-teal-400 border border-teal-500/20'
                          : 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20'
                      }`}>
                        {r.status}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-charcoal-400 pt-1">
                      <span>Model: <span className="font-mono text-charcoal-300">{r.model_used || 'default'}</span></span>
                      <span>{new Date(r.created_at).toLocaleString()}</span>
                    </div>
                    {r.final_output && (
                      <p className="text-xs text-charcoal-200 bg-charcoal-900/60 p-2 rounded line-clamp-2">
                        {r.final_output}
                      </p>
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
