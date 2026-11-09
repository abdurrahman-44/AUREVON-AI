import React, { useState, useEffect } from 'react';
import { X, Upload, FileText, Trash2, Search, CheckCircle, AlertCircle, Layers } from 'lucide-react';
import { uploadDocument, fetchDocuments, deleteDocument, queryDocuments } from '../../services/api';

interface DocumentsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const DocumentsModal: React.FC<DocumentsModalProps> = ({ isOpen, onClose }) => {
  const [documents, setDocuments] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // RAG Search test
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
    } catch (e) {
      console.error('Failed to load documents:', e);
    }
  };

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
    if (!confirm('Delete this document and all its indexed chunks?')) return;
    try {
      await deleteDocument(id);
      setDocuments((prev) => prev.filter((d) => d.id !== id));
    } catch (e) {
      console.error('Failed to delete document:', e);
    }
  };

  const handleRAGSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const res = await queryDocuments(searchQuery.trim(), 3);
      setSearchResults(res.results || []);
    } catch (e) {
      console.error('RAG search failed:', e);
    } finally {
      setSearching(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-2xl bg-charcoal-900 border border-charcoal-800 rounded-2xl shadow-2xl p-6 sm:p-8 max-h-[90vh] flex flex-col">
        {/* Close */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-charcoal-400 hover:text-white hover:bg-charcoal-800 transition-colors"
        >
          <X size={18} />
        </button>

        <h2 className="text-xl font-bold text-white tracking-tight mb-1">Document Intelligence & RAG</h2>
        <p className="text-xs text-charcoal-400 mb-6">
          Upload PDFs, DOCX, TXT, CSV, or code files. AUREVON automatically extracts, chunks, and indexes them for grounded question answering.
        </p>

        {/* Upload Drop Area */}
        <div className="mb-6">
          <label className="border-2 border-dashed border-charcoal-700 hover:border-brand-500 rounded-2xl p-6 flex flex-col items-center justify-center cursor-pointer bg-charcoal-800/30 hover:bg-charcoal-800/60 transition-all">
            <Upload size={24} className="text-brand-400 mb-2" />
            <span className="text-xs font-semibold text-white">
              {uploading ? 'Extracting & Indexing Chunks...' : 'Click or drop files to upload'}
            </span>
            <span className="text-[11px] text-charcoal-500 mt-1">
              Supported: PDF, DOCX, TXT, CSV, Markdown, Code (Max 25MB)
            </span>
            <input
              type="file"
              onChange={handleFileUpload}
              disabled={uploading}
              className="hidden"
              accept=".pdf,.docx,.txt,.md,.csv,.json,.py,.js,.ts"
            />
          </label>

          {uploadError && (
            <div className="mt-2 p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
              <AlertCircle size={14} />
              <span>{uploadError}</span>
            </div>
          )}
        </div>

        {/* Documents List */}
        <div className="flex-1 overflow-y-auto space-y-2 pr-1 mb-6">
          <h3 className="text-xs font-semibold text-charcoal-300 uppercase tracking-wider mb-2">
            Indexed Documents ({documents.length})
          </h3>

          {documents.length === 0 ? (
            <div className="p-6 text-center text-xs text-charcoal-500 bg-charcoal-800/20 rounded-xl border border-charcoal-800">
              No documents uploaded yet. Upload a document above to ground your AI conversations.
            </div>
          ) : (
            documents.map((doc) => (
              <div
                key={doc.id}
                className="p-3.5 rounded-xl bg-charcoal-800/40 border border-charcoal-700/60 flex items-center justify-between"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="p-2 rounded-lg bg-charcoal-800 text-brand-400">
                    <FileText size={16} />
                  </div>
                  <div className="min-w-0">
                    <span className="block text-xs font-semibold text-white truncate">{doc.filename}</span>
                    <span className="block text-[11px] text-charcoal-400 mt-0.5">
                      {doc.chunk_count} chunks • {Math.round(doc.file_size_bytes / 1024)} KB • Status:{' '}
                      <span className="text-emerald-400 font-medium">{doc.processing_status}</span>
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => handleDelete(doc.id)}
                  className="p-1.5 rounded-lg text-charcoal-400 hover:text-rose-400 hover:bg-charcoal-700/50 transition-colors"
                  title="Delete Document"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))
          )}
        </div>

        {/* Semantic Search Tester */}
        <div className="border-t border-charcoal-800 pt-4">
          <h4 className="text-xs font-semibold text-charcoal-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <Layers size={13} className="text-brand-400" />
            <span>Test RAG Vector Retrieval</span>
          </h4>

          <form onSubmit={handleRAGSearch} className="flex gap-2 mb-3">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Query indexed chunks (e.g. 'What are the system specifications?')"
              className="flex-1 bg-charcoal-800 border border-charcoal-700 rounded-xl px-3 py-1.5 text-xs text-white placeholder-charcoal-500 focus:outline-none focus:border-brand-500"
            />
            <button
              type="submit"
              disabled={searching || !searchQuery.trim()}
              className="px-3 py-1.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold transition-all disabled:opacity-50 flex items-center gap-1"
            >
              <Search size={13} />
              <span>{searching ? 'Searching...' : 'Test Search'}</span>
            </button>
          </form>

          {searchResults.length > 0 && (
            <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
              {searchResults.map((r, i) => (
                <div key={i} className="p-2.5 rounded-lg bg-charcoal-800/60 border border-charcoal-700/60 text-xs">
                  <div className="flex items-center justify-between text-[11px] text-brand-300 font-semibold mb-1">
                    <span>
                      {r.filename} {r.page_number ? `(Page ${r.page_number})` : ''}
                    </span>
                    <span className="text-emerald-400 font-mono">{Math.round(r.similarity * 100)}% match</span>
                  </div>
                  <p className="text-charcoal-300 text-[11px] line-clamp-2 leading-relaxed">{r.content}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
