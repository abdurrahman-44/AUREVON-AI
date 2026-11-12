import React, { useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  ChevronDown,
  Image as ImageIcon,
  Lock,
  Send,
  Sliders,
  Square,
  X,
} from 'lucide-react';
import { ModelInfo } from '../../types';

interface ComposerProps {
  input: string;
  setInput: (value: string) => void;
  onSend: (text?: string, images?: string[]) => void;
  onStop: () => void;
  isStreaming: boolean;
  selectedModel: string;
  models: ModelInfo[];
  onSelectModel: (modelId: string) => void;
  allowModelSwitching: boolean;
  canManageModels?: boolean;
  onOpenModelManagement?: () => void;
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
  disabled = false,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [attachedImages, setAttachedImages] = useState<string[]>([]);

  const activeModel = models.find((m) => m.id === selectedModel);
  const supportsVision = activeModel?.capabilities?.vision ?? false;

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [input]);

  const handleTriggerSend = () => {
    if (!isStreaming && (input.trim() || attachedImages.length > 0)) {
      onSend(input, attachedImages.length > 0 ? attachedImages : undefined);
      setAttachedImages([]);
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
      alert('Please select an image file.');
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

  const removeImage = (index: number) => {
    setAttachedImages((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <div className="px-4 sm:px-6 pb-4 pt-2 max-w-3xl w-full mx-auto">
      <div className="rounded-2xl border border-line bg-surface shadow-sm focus-within:border-line-strong transition-colors">
        {attachedImages.length > 0 && (
          <div className="px-3.5 pt-3 flex flex-wrap items-center gap-2">
            {attachedImages.map((imgSrc, idx) => (
              <div key={idx} className="relative rounded-xl overflow-hidden border border-line bg-elevated">
                <img src={imgSrc} alt="attachment" className="w-14 h-14 object-cover" />
                <button
                  type="button"
                  onClick={() => removeImage(idx)}
                  className="absolute top-1 right-1 p-0.5 rounded-full bg-black/75 text-white hover:bg-rose-600"
                  title="Remove attachment"
                >
                  <X size={11} />
                </button>
              </div>
            ))}
            {!supportsVision && (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-500/10 border border-amber-500/25 text-amber-500 text-xs">
                <AlertTriangle size={12} />
                <span>Active model `{selectedModel}` is text-only.</span>
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
          ref={fileInputRef}
          onChange={handleImageSelect}
          accept="image/*"
          className="hidden"
        />

        <div className="px-3 pb-2.5 flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
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
              onClick={() => fileInputRef.current?.click()}
              className="p-1.5 rounded-lg border border-line bg-canvas text-ink-muted hover:text-ink transition-colors"
              title="Attach image"
            >
              <ImageIcon size={14} />
            </button>

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
              disabled={(!input.trim() && attachedImages.length === 0) || disabled}
              className={`p-2 rounded-xl transition-colors ${
                (input.trim() || attachedImages.length > 0) && !disabled
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
        AUREVON AI may make mistakes. Verify critical information independently.
      </p>
    </div>
  );
};
