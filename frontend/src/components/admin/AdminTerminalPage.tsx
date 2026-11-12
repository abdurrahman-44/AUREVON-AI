import React, { useEffect, useRef, useState } from 'react';
import { AlertTriangle, Check, Copy, Play, ShieldAlert, Terminal as TerminalIcon, Trash2 } from 'lucide-react';
import { executeAdminTerminalCommand, fetchAdminTerminalCommands } from '../../services/api';
import { TerminalCommandInfo, TerminalExecuteResponse } from '../../types';

interface TranscriptEntry {
  id: string;
  input: string;
  result: TerminalExecuteResponse;
}

export const AdminTerminalPage: React.FC = () => {
  const [commands, setCommands] = useState<TerminalCommandInfo[]>([]);
  const [commandInput, setCommandInput] = useState('');
  const [history, setHistory] = useState<string[]>([]);
  const [historyIdx, setHistoryIdx] = useState(-1);
  const [entries, setEntries] = useState<TranscriptEntry[]>([]);
  const [running, setRunning] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [pendingConfirm, setPendingConfirm] = useState<{ command: string; token: string; message: string } | null>(
    null
  );

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchAdminTerminalCommands()
      .then(setCommands)
      .catch((err) => setErrorMsg(err.message || 'Failed to load command catalog'));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries]);

  const runCommand = async (raw: string, confirmToken?: string) => {
    const trimmed = raw.trim();
    if (!trimmed || running) return;

    if (trimmed.toLowerCase() === 'clear') {
      setEntries([]);
      setCommandInput('');
      setPendingConfirm(null);
      return;
    }

    setRunning(true);
    setErrorMsg(null);

    try {
      const res = await executeAdminTerminalCommand(trimmed, confirmToken);
      if (res.requires_confirmation && res.confirm_token) {
        setPendingConfirm({
          command: res.command,
          token: res.confirm_token,
          message: res.output,
        });
      } else {
        setPendingConfirm(null);
      }

      setEntries((prev) => [
        ...prev,
        {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          input: trimmed,
          result: res,
        },
      ]);

      setHistory((prev) => [trimmed, ...prev.filter((h) => h !== trimmed)].slice(0, 40));
      setHistoryIdx(-1);
      if (!confirmToken) {
        setCommandInput('');
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Terminal request failed');
    } finally {
      setRunning(false);
      inputRef.current?.focus();
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runCommand(commandInput);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (history.length === 0) return;
      const next = Math.min(history.length - 1, historyIdx + 1);
      setHistoryIdx(next);
      setCommandInput(history[next]);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIdx <= 0) {
        setHistoryIdx(-1);
        setCommandInput('');
      } else {
        const next = historyIdx - 1;
        setHistoryIdx(next);
        setCommandInput(history[next]);
      }
    }
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 1500);
    });
  };

  const categories = Array.from(new Set(commands.map((c) => c.category)));

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
      <aside className="rounded-xl border border-line bg-surface p-4 lg:col-span-4 space-y-4">
        <div>
          <h2 className="text-sm font-semibold text-ink">Approved Command Registry</h2>
          <p className="mt-0.5 text-xs text-ink-muted">
            Allowlist-enforced diagnostics &amp; maintenance. No OS shell or arbitrary SQL execution.
          </p>
        </div>

        <div className="max-h-[540px] space-y-4 overflow-y-auto pr-1">
          {categories.map((cat) => (
            <div key={cat}>
              <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-ink-muted">{cat}</div>
              <div className="space-y-1.5">
                {commands
                  .filter((c) => c.category === cat)
                  .map((cmd) => (
                    <button
                      key={cmd.command}
                      type="button"
                      onClick={() => runCommand(cmd.command)}
                      disabled={running}
                      className="flex w-full items-start justify-between gap-2 rounded-lg border border-line bg-elevated/60 px-3 py-2 text-left hover:border-accent/50 hover:bg-elevated transition disabled:opacity-50"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <code className="text-xs font-semibold text-accent">{cmd.usage}</code>
                          {cmd.requires_confirmation && (
                            <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-medium text-amber-500">
                              confirm
                            </span>
                          )}
                        </div>
                        <div className="mt-0.5 text-[11px] text-ink-secondary">{cmd.description}</div>
                      </div>
                      <Play className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-muted" />
                    </button>
                  ))}
              </div>
            </div>
          ))}
        </div>
      </aside>

      <section className="flex flex-col rounded-xl border border-line bg-[#0d1016] text-zinc-100 shadow-lg lg:col-span-8">
        <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
          <div className="flex items-center gap-2">
            <TerminalIcon className="h-4 w-4 text-indigo-400" />
            <span className="font-mono text-xs font-semibold tracking-wide text-zinc-200">
              aurevon-ops-console
            </span>
            <span className="rounded bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-400">
              AUDITED
            </span>
          </div>

          <button
            type="button"
            onClick={() => {
              setEntries([]);
              setPendingConfirm(null);
            }}
            className="flex items-center gap-1.5 rounded-lg border border-zinc-700 px-2.5 py-1 text-[11px] text-zinc-300 hover:bg-zinc-800 transition"
          >
            <Trash2 className="h-3 w-3" />
            Clear Buffer
          </button>
        </div>

        {pendingConfirm && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-xs text-amber-200">
            <div className="flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 shrink-0 text-amber-400" />
              <span>{pendingConfirm.message}</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => runCommand(pendingConfirm.command, pendingConfirm.token)}
                disabled={running}
                className="rounded-lg bg-amber-500 px-3 py-1 font-semibold text-zinc-950 hover:bg-amber-400 transition"
              >
                Confirm &amp; Execute
              </button>
              <button
                type="button"
                onClick={() => setPendingConfirm(null)}
                className="rounded-lg border border-zinc-600 px-2.5 py-1 text-zinc-300 hover:bg-zinc-800"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {errorMsg && (
          <div className="flex items-center gap-2 border-b border-rose-500/30 bg-rose-500/10 px-4 py-2 text-xs text-rose-300">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        <div className="h-[460px] flex-1 overflow-y-auto p-4 font-mono text-xs leading-relaxed space-y-4">
          {entries.length === 0 ? (
            <div className="text-zinc-400 space-y-1.5 py-4">
              <p className="text-zinc-300 font-semibold">AUREVON Operations Terminal Ready.</p>
              <p>Type &apos;help&apos; or select a command from the left registry to begin.</p>
              <p className="text-[11px] text-zinc-500">
                Security Notice: Shell operators (;|&amp;&amp;$&gt;&lt;), arbitrary SQL, and sensitive fields are rejected and audited.
              </p>
            </div>
          ) : (
            entries.map((entry) => {
              const badgeColor =
                entry.result.exit_code === 0
                  ? 'bg-emerald-500/15 text-emerald-400'
                  : entry.result.requires_confirmation
                    ? 'bg-amber-500/15 text-amber-300'
                    : 'bg-rose-500/15 text-rose-400';
              return (
                <div key={entry.id} className="space-y-1.5 border-b border-zinc-800/80 pb-3 last:border-b-0">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-indigo-400">owner@aurevon:~$</span>
                      <span className="font-semibold text-white">{entry.input}</span>
                    </div>
                    <div className="flex items-center gap-2 text-[10px]">
                      <span className={`rounded px-1.5 py-0.5 font-semibold ${badgeColor}`}>
                        {entry.result.status} ({entry.result.duration_ms}ms)
                      </span>
                      <button
                        type="button"
                        onClick={() => handleCopy(entry.id, entry.result.output)}
                        className="rounded border border-zinc-700 p-1 text-zinc-400 hover:text-zinc-200"
                        title="Copy output"
                      >
                        {copiedId === entry.id ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                      </button>
                    </div>
                  </div>
                  <pre className="whitespace-pre-wrap break-words rounded-lg bg-zinc-900/90 p-3 text-zinc-200 border border-zinc-800">
                    {entry.result.output}
                  </pre>
                </div>
              );
            })
          )}
          <div ref={bottomRef} />
        </div>

        <form onSubmit={handleSubmit} className="flex items-center gap-2 border-t border-zinc-800 bg-zinc-950/60 px-4 py-3">
          <span className="font-mono text-xs font-semibold text-indigo-400">$</span>
          <input
            ref={inputRef}
            type="text"
            value={commandInput}
            onChange={(e) => setCommandInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter approved command (e.g. help, status, db stats, ai test, system diagnostics)..."
            className="flex-1 bg-transparent font-mono text-xs text-white placeholder-zinc-500 focus:outline-none"
            disabled={running}
          />
          <button
            type="submit"
            disabled={running || !commandInput.trim()}
            className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 transition"
          >
            {running ? 'Running...' : 'Execute'}
          </button>
        </form>
      </section>
    </div>
  );
};
