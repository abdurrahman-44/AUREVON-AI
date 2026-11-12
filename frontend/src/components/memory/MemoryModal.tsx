import React, { useEffect, useState } from 'react';
import { AlertCircle, Brain, Plus, Search, ToggleLeft, ToggleRight, Trash2, X } from 'lucide-react';
import { createMemory, deleteMemory, fetchMemories, updateMemory } from '../../services/api';

interface MemoryModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const MemoryModal: React.FC<MemoryModalProps> = ({ isOpen, onClose }) => {
  const [memories, setMemories] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [newContent, setNewContent] = useState('');
  const [newCategory, setNewCategory] = useState('preference');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadMemories();
    }
  }, [isOpen]);

  const loadMemories = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchMemories();
      setMemories(data);
    } catch (e: any) {
      setError(e.message || 'Failed to load memories');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newContent.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await createMemory(newContent.trim(), newCategory);
      setNewContent('');
      await loadMemories();
    } catch (err: any) {
      setError(err.message || 'Failed to add memory');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleActive = async (m: any) => {
    try {
      const updated = await updateMemory(m.id, { is_active: !m.is_active });
      setMemories((prev) => prev.map((x) => (x.id === m.id ? updated : x)));
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteMemory(id);
      setMemories((prev) => prev.filter((x) => x.id !== id));
    } catch (err: any) {
      setError(err.message);
    }
  };

  const filtered = memories.filter(
    (m) =>
      m.content.toLowerCase().includes(searchTerm.toLowerCase()) ||
      m.category.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl rounded-2xl border border-line bg-surface shadow-xl flex flex-col max-h-[85vh] overflow-hidden">
        <div className="px-6 py-4 border-b border-line flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Brain size={17} className="text-accent" />
            <div>
              <h2 className="text-sm font-semibold text-ink">Memory Manager</h2>
              <p className="text-[11px] text-ink-secondary">Save persistent preferences and facts across conversations</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-ink-muted hover:text-ink hover:bg-elevated">
            <X size={16} />
          </button>
        </div>

        <div className="p-6 overflow-y-auto space-y-5">
          {error && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/25 text-xs text-rose-500 flex items-center gap-2">
              <AlertCircle size={14} />
              {error}
            </div>
          )}

          <form onSubmit={handleCreate} className="flex flex-col sm:flex-row gap-2">
            <input
              type="text"
              value={newContent}
              onChange={(e) => setNewContent(e.target.value)}
              placeholder="Remember that I prefer concise TypeScript examples..."
              className="flex-1 px-3.5 py-2 rounded-xl border border-line bg-canvas text-xs text-ink focus:outline-none focus:border-accent"
            />
            <select
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
              className="px-3 py-2 rounded-xl border border-line bg-canvas text-xs text-ink"
            >
              <option value="preference">Preference</option>
              <option value="project">Project</option>
              <option value="fact">Fact</option>
              <option value="general">General</option>
            </select>
            <button
              type="submit"
              disabled={submitting || !newContent.trim()}
              className="inline-flex items-center justify-center gap-1 px-4 py-2 rounded-xl bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-xs font-medium"
            >
              <Plus size={13} />
              Add
            </button>
          </form>

          <div className="relative">
            <Search size={13} className="absolute left-3 top-2.5 text-ink-muted" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search memories..."
              className="w-full pl-8 pr-3 py-2 rounded-xl border border-line bg-canvas text-xs text-ink focus:outline-none focus:border-accent"
            />
          </div>

          <div className="space-y-2">
            {loading ? (
              <p className="text-xs text-ink-muted">Loading memories...</p>
            ) : filtered.length === 0 ? (
              <p className="text-xs text-ink-muted">No matching memories found.</p>
            ) : (
              filtered.map((m) => (
                <div
                  key={m.id}
                  className="flex items-start justify-between gap-3 rounded-xl border border-line bg-canvas px-3.5 py-3 text-xs"
                >
                  <div className="space-y-1 min-w-0">
                    <span className="inline-block px-2 py-0.5 rounded bg-elevated text-ink-secondary text-[10px] uppercase font-mono">
                      {m.category}
                    </span>
                    <p className={`text-ink leading-relaxed ${!m.is_active ? 'opacity-50 line-through' : ''}`}>
                      {m.content}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      onClick={() => handleToggleActive(m)}
                      className="p-1.5 rounded-lg text-ink-secondary hover:text-ink hover:bg-elevated"
                      title={m.is_active ? 'Disable' : 'Enable'}
                    >
                      {m.is_active ? <ToggleRight size={16} className="text-accent" /> : <ToggleLeft size={16} />}
                    </button>
                    <button
                      onClick={() => handleDelete(m.id)}
                      className="p-1.5 rounded-lg text-ink-muted hover:text-rose-500 hover:bg-elevated"
                      title="Delete"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
