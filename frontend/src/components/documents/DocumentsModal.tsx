import React, { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle, FileText, Search, Trash2, Upload, X } from 'lucide-react';
import { deleteDocument, fetchDocuments, queryDocuments, uploadDocument } from '../../services/api';

interface DocumentsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const DocumentsModal: React.FC<DocumentsModalProps> = ({ isOpen, onClose }) => {
  const [documents, setDocuments] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadDocuments();
    }
  }, [isOpen]);

  const loadDocuments = async () => {
    try {
      const data = await fetchDocuments();
      setDocuments(data);
    } catch (e: any) {
      setUploadError(e.message || 'Failed to load documents');
    }
  };

  if (!isOpen) return null;

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      await uploadDocument(file);
      await loadDocuments();
      e.target.value = '';
    } catch (err: any) {
      setUploadError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteDocument(id);
      setDocuments((prev) => prev.filter((d) => d.id !== id));
    } catch (err: any) {
      setUploadError(err.message || 'Failed to delete document');
    }
  };

  const handleQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);
    setUploadError(null);
    try {
      const data = await queryDocuments(searchQuery.trim(), 4);
      setSearchResults(data.results || []);
    } catch (err: any) {
      setUploadError(err.message || 'Search failed');
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl rounded-2xl border border-line bg-surface shadow-xl flex flex-col max-h-[85vh] overflow-hidden">
        <div className="px-6 py-4 border-b border-line flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <FileText size={17} className="text-accent" />
            <div>
              <h2 className="text-sm font-semibold text-ink">Documents & RAG Knowledge Base</h2>
              <p className="text-[11px] text-ink-secondary">Upload private files for grounded context retrieval</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-ink-muted hover:text-ink hover:bg-elevated">
            <X size={16} />
          </button>
        </div>

        <div className="p-6 overflow-y-auto space-y-5">
          {uploadError && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/25 text-xs text-rose-500 flex items-center gap-2">
              <AlertCircle size={14} />
              {uploadError}
            </div>
          )}

          <label className="flex flex-col items-center justify-center gap-2 p-5 rounded-2xl border border-dashed border-line-strong bg-canvas hover:bg-elevated/50 cursor-pointer transition-colors">
            <Upload size={18} className="text-ink-muted" />
            <div className="text-xs font-medium text-ink">
              {uploading ? 'Indexing document...' : 'Upload PDF, DOCX, TXT, MD, CSV, JSON, or Code'}
            </div>
            <input type="file" onChange={handleFileUpload} disabled={uploading} className="hidden" />
          </label>

          {/* Uploaded List */}
          <div className="space-y-2">
            <h3 className="text-xs font-medium text-ink-secondary">Indexed Files ({documents.length})</h3>
            {documents.length === 0 ? (
              <p className="text-xs text-ink-muted py-2">No documents indexed in this workspace yet.</p>
            ) : (
              documents.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center justify-between px-3.5 py-2.5 rounded-xl border border-line bg-canvas text-xs"
                >
                  <div className="min-w-0">
                    <div className="font-medium text-ink truncate">{doc.filename}</div>
                    <div className="text-[11px] text-ink-muted flex items-center gap-2">
                      <span>{doc.chunk_count} chunks</span>
                      <span>•</span>
                      <span className="inline-flex items-center gap-1 text-emerald-500">
                        <CheckCircle size={11} />
                        {doc.processing_status}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(doc.id)}
                    className="p-1.5 rounded-lg text-ink-muted hover:text-rose-500 hover:bg-elevated"
                    title="Delete document"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))
            )}
          </div>

          {/* Semantic Search Test */}
          <div className="pt-3 border-t border-line space-y-3">
            <form onSubmit={handleQuery} className="flex gap-2">
              <div className="relative flex-1">
                <Search size={13} className="absolute left-3 top-2.5 text-ink-muted" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Test semantic retrieval across uploaded files..."
                  className="w-full pl-8 pr-3 py-2 rounded-xl border border-line bg-canvas text-xs text-ink focus:outline-none focus:border-accent"
                />
              </div>
              <button
                type="submit"
                disabled={searching || !searchQuery.trim()}
                className="px-4 py-2 rounded-xl bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-xs font-medium"
              >
                {searching ? 'Searching...' : 'Query'}
              </button>
            </form>

            {searchResults.length > 0 && (
              <div className="space-y-2">
                {searchResults.map((hit, i) => (
                  <div key={i} className="rounded-xl border border-line bg-canvas p-3 text-xs space-y-1">
                    <div className="flex items-center justify-between text-[11px] text-ink-muted font-mono">
                      <span>{hit.filename}</span>
                      <span>Score: {(hit.similarity * 100).toFixed(0)}%</span>
                    </div>
                    <p className="text-ink-secondary leading-relaxed">{hit.content}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
