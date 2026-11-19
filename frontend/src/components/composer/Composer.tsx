import React, { useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  ChevronDown,
  Cloud,
  FileText,
  Globe,
  Image as ImageIcon,
  Loader2,
  Lock,
  Paperclip,
  Send,
  Sliders,
  Square,
  X,
} from 'lucide-react';
import { uploadDocument } from '../../services/api';
import { ModelInfo } from '../../types';

export interface AttachedDocBadge {
  id: string;
  filename: string;
  chunk_count?: number;
}

interface ComposerProps {
  input: string;
  setInput: (value: string) => void;
  onSend: (
    text?: string,
    images?: string[],
    options?: { documentIds?: string[]; webSearch?: boolean; allowCloud?: boolean }
  ) => void;
  onStop: () => void;
  isStreaming: boolean;
  selectedModel: string;
  models: ModelInfo[];
  onSelectModel: (modelId: string) => void;
  allowModelSwitching: boolean;
  canManageModels?: boolean;
  onOpenModelManagement?: () => void;
  cloudAvailable?: boolean;
  disabled?: boolean;
}

export const Composer: React.FC<ComposerProps> = ({
  input,
  setInput,
  onSend,
  onStop,
  isStreaming,
  selectedModel,
  models,
  onSelectModel,
  allowModelSwitching,
  canManageModels = false,
  onOpenModelManagement,
  cloudAvailable = false,
  disabled = false,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const docInputRef = useRef<HTMLInputElement>(null);
  const [attachedImages, setAttachedImages] = useState<string[]>([]);
  const [attachedDocs, setAttachedDocs] = useState<AttachedDocBadge[]>([]);
  const [uploadingDoc, setUploadingDoc] = useState(false);
  const [attachError, setAttachError] = useState<string | null>(null);
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const [allowCloud, setAllowCloud] = useState(false);

  const activeModel = models.find((m) => m.id === selectedModel);
  const supportsVision = activeModel?.capabilities?.vision ?? false;

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [input]);

  const handleTriggerSend = () => {
    if (!isStreaming && !uploadingDoc && (input.trim() || attachedImages.length > 0 || attachedDocs.length > 0)) {
      const promptText =
        input.trim() ||
        (attachedDocs.length > 0
          ? `Summarize and analyze the attached document${attachedDocs.length > 1 ? 's' : ''}: ${attachedDocs.map((d) => d.filename).join(', ')}`
          : input);
      onSend(promptText, attachedImages.length > 0 ? attachedImages : undefined, {
        documentIds: attachedDocs.length > 0 ? attachedDocs.map((d) => d.id) : undefined,
        webSearch: webSearchEnabled,
        allowCloud,
      });
      setAttachedImages([]);
      setAttachedDocs([]);
      setAttachError(null);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleTriggerSend();
    }
  };

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setAttachError('Please select a valid image file.');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        setAttachedImages((prev) => [...prev, reader.result as string]);
      }
    };
    reader.readAsDataURL(file);
    e.target.value = '';
  };

  const handleDocumentSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setAttachError(null);
    setUploadingDoc(true);
    try {
      const uploaded = await uploadDocument(file);
      setAttachedDocs((prev) => [
        ...prev.filter((d) => d.id !== uploaded.id),
        { id: uploaded.id, filename: uploaded.filename, chunk_count: uploaded.chunk_count },
      ]);
    } catch (err: any) {
      setAttachError(err.message || 'Failed to upload attached document');
    } finally {
      setUploadingDoc(false);
    }
  };

  const removeImage = (index: number) => {
    setAttachedImages((prev) => prev.filter((_, i) => i !== index));
  };

  const removeDoc = (docId: string) => {
    setAttachedDocs((prev) => prev.filter((d) => d.id !== docId));
  };

  return (
    <div className="px-4 sm:px-6 pb-4 pt-2 max-w-3xl w-full mx-auto">
      <div className="rounded-2xl border border-line bg-surface shadow-sm focus-within:border-line-strong transition-colors">
        {(attachedImages.length > 0 || attachedDocs.length > 0 || attachError) && (
          <div className="px-3.5 pt-3 flex flex-wrap items-center gap-2">
            {attachedImages.map((imgSrc, idx) => (
              <div key={idx} className="relative rounded-xl overflow-hidden border border-line bg-elevated">
                <img src={imgSrc} alt="attachment" className="w-14 h-14 object-cover" />
                <button
                  type="button"
                  onClick={() => removeImage(idx)}
                  className="absolute top-1 right-1 p-0.5 rounded-full bg-black/75 text-white hover:bg-rose-600"
                  title="Remove image attachment"
                >
                  <X size={11} />
                </button>
              </div>
            ))}

            {attachedDocs.map((doc) => (
              <div
                key={doc.id}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border border-accent/30 bg-accent/10 text-xs text-ink"
              >
                <FileText size={13} className="text-accent shrink-0" />
                <span className="max-w-[160px] truncate font-medium">{doc.filename}</span>
                {doc.chunk_count !== undefined && (
                  <span className="text-[10px] text-ink-muted">({doc.chunk_count})</span>
                )}
                <button
                  type="button"
                  onClick={() => removeDoc(doc.id)}
                  className="text-ink-muted hover:text-rose-500 ml-0.5"
                  title="Detach document"
                >
                  <X size={12} />
                </button>
              </div>
            ))}

            {attachedImages.length > 0 && !supportsVision && (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-500/10 border border-amber-500/25 text-amber-500 text-xs">
                <AlertTriangle size={12} />
                <span>Active model `{selectedModel}` is text-only.</span>
              </div>
            )}

            {attachError && (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-rose-500/10 border border-rose-500/25 text-rose-500 text-xs">
                <AlertTriangle size={12} />
                <span>{attachError}</span>
              </div>
            )}
          </div>
        )}

        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Message AUREVON..."
          rows={1}
          disabled={disabled}
          className="w-full bg-transparent px-4 pt-3.5 pb-2 text-sm sm:text-[15px] text-ink placeholder-ink-muted focus:outline-none resize-none leading-relaxed"
        />

        <input
          type="file"
          ref={imageInputRef}
          onChange={handleImageSelect}
          accept="image/*"
          className="hidden"
        />
        <input
          type="file"
          ref={docInputRef}
          onChange={handleDocumentSelect}
          accept=".pdf,.docx,.xlsx,.txt,.md,.csv,.json,.py,.js,.ts,.log"
          className="hidden"
        />

        <div className="px-3 pb-2.5 flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 flex-wrap">
            {allowModelSwitching ? (
              <div className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-line bg-canvas text-xs text-ink-secondary">
                <select
                  value={selectedModel}
                  onChange={(e) => onSelectModel(e.target.value)}
                  className="bg-transparent text-ink text-xs font-mono focus:outline-none cursor-pointer"
                >
                  {models.map((m) => (
                    <option key={m.id} value={m.id} className="bg-surface text-ink">
                      {m.name}
                    </option>
                  ))}
                </select>
                <ChevronDown size={11} className="text-ink-muted pointer-events-none" />
              </div>
            ) : (
              <div
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-line bg-canvas text-[11px] font-mono text-ink-secondary"
                title="Model managed centrally by platform owner"
              >
                <Lock size={11} className="text-ink-muted" />
                <span>{selectedModel}</span>
              </div>
            )}

            <button
              type="button"
              onClick={() => docInputRef.current?.click()}
              disabled={uploadingDoc || isStreaming}
              className="inline-flex items-center gap-1 p-1.5 px-2 rounded-lg border border-line bg-canvas text-xs text-ink-muted hover:text-ink transition-colors disabled:opacity-50"
              title="Attach document (.pdf, .docx, .xlsx, .csv, .txt, code)"
            >
              {uploadingDoc ? <Loader2 size={13} className="animate-spin text-accent" /> : <Paperclip size={13} />}
              <span className="hidden sm:inline text-[11px]">Attach</span>
            </button>

            <button
              type="button"
              onClick={() => imageInputRef.current?.click()}
              className="p-1.5 rounded-lg border border-line bg-canvas text-ink-muted hover:text-ink transition-colors"
              title="Attach image"
            >
              <ImageIcon size={14} />
            </button>

            <button
              type="button"
              onClick={() => setWebSearchEnabled((v) => !v)}
              className={`inline-flex items-center gap-1 p-1.5 px-2 rounded-lg border text-[11px] transition-colors ${
                webSearchEnabled
                  ? 'border-accent/50 bg-accent/15 text-accent font-medium'
                  : 'border-line bg-canvas text-ink-muted hover:text-ink'
              }`}
              title="Toggle live web search for this turn"
            >
              <Globe size={13} />
              <span className="hidden sm:inline">Web</span>
            </button>

            {cloudAvailable && (
              <button
                type="button"
                onClick={() => setAllowCloud((v) => !v)}
                className={`inline-flex items-center gap-1 p-1.5 px-2 rounded-lg border text-[11px] transition-colors ${
                  allowCloud
                    ? 'border-amber-500/50 bg-amber-500/15 text-amber-500 font-medium'
                    : 'border-line bg-canvas text-ink-muted hover:text-ink'
                }`}
                title="Explicit consent to allow optional cloud inference for this turn"
              >
                <Cloud size={13} />
                <span className="hidden sm:inline">Cloud OK</span>
              </button>
            )}

            {canManageModels && onOpenModelManagement && (
              <button
                type="button"
                onClick={onOpenModelManagement}
                className="p-1.5 rounded-lg border border-line bg-canvas text-ink-muted hover:text-ink transition-colors"
                title="Model runtime overview"
              >
                <Sliders size={13} />
              </button>
            )}
          </div>

          {isStreaming ? (
            <button
              type="button"
              onClick={onStop}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-medium transition-colors"
            >
              <Square size={12} fill="currentColor" />
              Stop
            </button>
          ) : (
            <button
              type="button"
              onClick={handleTriggerSend}
              disabled={
                (!input.trim() && attachedImages.length === 0 && attachedDocs.length === 0) ||
                uploadingDoc ||
                disabled
              }
              className={`p-2 rounded-xl transition-colors ${
                (input.trim() || attachedImages.length > 0 || attachedDocs.length > 0) && !uploadingDoc && !disabled
                  ? 'bg-accent hover:bg-accent-hover text-white'
                  : 'bg-elevated text-ink-muted cursor-not-allowed'
              }`}
              title="Send message"
            >
              <Send size={15} />
            </button>
          )}
        </div>
      </div>

      <p className="text-[11px] text-center text-ink-muted mt-2">
        AUREVON AI runs local-first inference. Verify critical outputs and citations independently.
      </p>
    </div>
  );
};
