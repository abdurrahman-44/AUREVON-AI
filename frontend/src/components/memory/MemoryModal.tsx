import React, { useState, useEffect } from 'react';
import { X, Brain, Trash2, Plus, Tag, ToggleLeft, ToggleRight, Search, AlertCircle } from 'lucide-react';
import { fetchMemories, createMemory, updateMemory, deleteMemory } from '../../services/api';

interface MemoryModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const MemoryModal: React.FC<MemoryModalProps> = ({ isOpen, onClose }) => {
  const [memories, setMemories] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  
  // New memory form state
  const [newContent, setNewContent] = useState('');
  const [newCategory, setNewCategory] = useState('preference');
  const [isSubmitting, setIsSubmitting] = useState(false);
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

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newContent.trim()) return;

    setIsSubmitting(true);
    setError(null);
    try {
      await createMemory(newContent.trim(), newCategory);
      setNewContent('');
      await loadMemories();
    } catch (err: any) {
      setError(err.message || 'Failed to create memory');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleActive = async (id: string, currentStatus: boolean) => {
    try {
      await updateMemory(id, { is_active: !currentStatus });
      setMemories(memories.map(m => m.id === id ? { ...m, is_active: !currentStatus } : m));
    } catch (err: any) {
      setError(err.message || 'Failed to update memory status');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this memory?')) return;
    try {
      await deleteMemory(id);
      setMemories(memories.filter(m => m.id !== id));
    } catch (err: any) {
      setError(err.message || 'Failed to delete memory');
    }
  };

  if (!isOpen) return null;

  const filteredMemories = memories.filter(m =>
    m.content.toLowerCase().includes(searchTerm.toLowerCase()) ||
    m.category.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-2xl bg-charcoal-900 border border-charcoal-700/80 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[88vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-charcoal-800">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-teal-500/10 text-teal-400">
              <Brain className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Long-Term Memory</h2>
              <p className="text-xs text-charcoal-400">Persistent user facts, preferences & cross-conversation context</p>
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
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Add Memory Form */}
          <form onSubmit={handleCreate} className="p-4 bg-charcoal-800/60 border border-charcoal-700/60 rounded-xl space-y-3">
            <div className="text-xs font-semibold uppercase tracking-wider text-charcoal-300">
              Add New Memory Fact
            </div>
            <textarea
              value={newContent}
              onChange={(e) => setNewContent(e.target.value)}
              placeholder="e.g., Prefers concise TypeScript examples without semicolons"
              rows={2}
              className="w-full bg-charcoal-900 border border-charcoal-700 rounded-lg p-2.5 text-sm text-charcoal-100 placeholder-charcoal-500 focus:outline-none focus:border-teal-500"
            />
            <div className="flex items-center justify-between pt-1">
              <div className="flex items-center space-x-2">
                <Tag className="w-4 h-4 text-charcoal-400" />
                <select
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value)}
                  className="bg-charcoal-900 border border-charcoal-700 rounded-lg px-2.5 py-1.5 text-xs text-charcoal-200 focus:outline-none focus:border-teal-500"
                >
                  <option value="preference">Preference</option>
                  <option value="fact">Fact</option>
                  <option value="project">Project</option>
                  <option value="instruction">Instruction</option>
                  <option value="general">General</option>
                </select>
              </div>
              <button
                type="submit"
                disabled={isSubmitting || !newContent.trim()}
                className="px-4 py-1.5 bg-teal-500 hover:bg-teal-600 disabled:opacity-50 text-white font-medium text-xs rounded-lg flex items-center space-x-1.5 transition"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>{isSubmitting ? 'Saving...' : 'Add Memory'}</span>
              </button>
            </div>
          </form>

          {/* Filter / Search */}
          <div className="flex items-center justify-between gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-charcoal-400" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search memories..."
                className="w-full pl-9 pr-3 py-1.5 bg-charcoal-800/80 border border-charcoal-700 rounded-lg text-xs text-charcoal-200 placeholder-charcoal-500 focus:outline-none focus:border-teal-500"
              />
            </div>
            <div className="text-xs text-charcoal-400">
              Total: <span className="text-teal-400 font-medium">{memories.length}</span>
            </div>
          </div>

          {/* Memories List */}
          <div className="space-y-2">
            {loading ? (
              <div className="text-center py-8 text-charcoal-400 text-xs">Loading memories...</div>
            ) : filteredMemories.length === 0 ? (
              <div className="text-center py-8 text-charcoal-400 text-xs">
                {memories.length === 0 ? 'No long-term memories stored yet. Add one above!' : 'No matching memories found.'}
              </div>
            ) : (
              filteredMemories.map((mem) => (
                <div
                  key={mem.id}
                  className={`p-3 rounded-xl border transition flex items-start justify-between gap-3 ${
                    mem.is_active
                      ? 'bg-charcoal-800/40 border-charcoal-700/60'
                      : 'bg-charcoal-900/60 border-charcoal-800/80 opacity-60'
                  }`}
                >
                  <div className="flex-1 space-y-1.5">
                    <div className="flex items-center space-x-2">
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider bg-teal-500/10 text-teal-400 border border-teal-500/20">
                        {mem.category}
                      </span>
                      <span className="text-[10px] text-charcoal-400">
                        {new Date(mem.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    <p className="text-xs text-charcoal-200 leading-relaxed">{mem.content}</p>
                  </div>

                  <div className="flex items-center space-x-2 shrink-0 pt-1">
                    <button
                      onClick={() => handleToggleActive(mem.id, mem.is_active)}
                      title={mem.is_active ? 'Disable memory' : 'Enable memory'}
                      className="text-charcoal-400 hover:text-teal-400 transition"
                    >
                      {mem.is_active ? (
                        <ToggleRight className="w-5 h-5 text-teal-400" />
                      ) : (
                        <ToggleLeft className="w-5 h-5 text-charcoal-500" />
                      )}
                    </button>
                    <button
                      onClick={() => handleDelete(mem.id)}
                      title="Delete memory"
                      className="text-charcoal-400 hover:text-red-400 transition"
                    >
                      <Trash2 className="w-4 h-4" />
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
