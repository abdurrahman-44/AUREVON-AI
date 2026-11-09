import React, { useRef, useEffect, useState } from 'react';
import { Send, Square, Sparkles, ChevronDown, Sliders, Image as ImageIcon, X, AlertTriangle } from 'lucide-react';
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
  onOpenModelManagement,
  disabled = false,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [attachedImages, setAttachedImages] = useState<string[]>([]);

  // Find selected model capabilities
  const activeModel = models.find((m) => m.id === selectedModel);
  const supportsVision = activeModel?.capabilities?.vision ?? false;

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleTriggerSend();
    }
  };

  const handleTriggerSend = () => {
    if (!isStreaming && (input.trim() || attachedImages.length > 0)) {
      onSend(input, attachedImages.length > 0 ? attachedImages : undefined);
      setAttachedImages([]);
    }
  };

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      alert('Please upload an image file (PNG, JPEG, WebP, etc.)');
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
    <div className="p-4 md:px-8 max-w-4xl w-full mx-auto">
      <div className="relative rounded-2xl bg-charcoal-900 border border-charcoal-800 shadow-2xl shadow-black/50 focus-within:border-charcoal-700 transition-all">
        {/* Attached Images Previews */}
        {attachedImages.length > 0 && (
          <div className="p-3 pb-0 flex flex-wrap items-center gap-2 border-b border-charcoal-800/60">
            {attachedImages.map((imgSrc, idx) => (
              <div key={idx} className="relative group rounded-xl overflow-hidden border border-charcoal-700 bg-charcoal-800">
                <img src={imgSrc} alt="attachment" className="w-16 h-16 object-cover" />
                <button
                  type="button"
                  onClick={() => removeImage(idx)}
                  className="absolute top-1 right-1 p-0.5 rounded-full bg-black/70 text-white hover:bg-red-600 transition"
                  title="Remove image"
                >
                  <X size={12} />
                </button>
              </div>
            ))}

            {!supportsVision && (
              <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs">
                <AlertTriangle size={13} className="shrink-0" />
                <span>Model '{selectedModel}' is text-only. Switch to a vision model (e.g., llava or gpt-4o).</span>
              </div>
            )}
          </div>
        )}

        {/* Input Textarea */}
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Message AUREVON AI... (Enter to send, Shift+Enter for new line)"
          rows={1}
          disabled={disabled}
          className="w-full bg-transparent px-4 pt-3.5 pb-12 text-sm sm:text-base text-charcoal-100 placeholder-charcoal-500 focus:outline-none resize-none leading-relaxed"
        />

        {/* Hidden File Input for Multimodal Image Upload */}
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleImageSelect}
          accept="image/*"
          className="hidden"
        />

        {/* Bottom Control Bar */}
        <div className="absolute bottom-2.5 left-3 right-3 flex items-center justify-between">
          {/* Model Selector & Multimodal Attachments */}
          <div className="relative flex items-center gap-1.5">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-charcoal-800/80 border border-charcoal-700/60 text-xs text-charcoal-300 hover:text-white hover:bg-charcoal-800 transition-colors">
              <Sparkles size={12} className="text-brand-400" />
              <select
                value={selectedModel}
                onChange={(e) => onSelectModel(e.target.value)}
                className="bg-transparent text-charcoal-200 text-xs font-mono focus:outline-none cursor-pointer pr-1"
              >
                {models.map((m) => (
                  <option key={m.id} value={m.id} className="bg-charcoal-900 text-charcoal-100">
                    {m.name} {m.size ? `(${m.size})` : ''}
                  </option>
                ))}
              </select>
              <ChevronDown size={11} className="text-charcoal-400 pointer-events-none" />
            </div>

            {/* Attach Image Button */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="p-1.5 rounded-lg bg-charcoal-800/80 border border-charcoal-700/60 text-charcoal-400 hover:text-teal-400 hover:bg-charcoal-800 transition-colors"
              title="Attach image (Multimodal Vision)"
            >
              <ImageIcon size={14} />
            </button>

            {onOpenModelManagement && (
              <button
                type="button"
                onClick={onOpenModelManagement}
                className="p-1 rounded-lg bg-charcoal-800/80 border border-charcoal-700/60 text-charcoal-400 hover:text-white hover:bg-charcoal-800 transition-colors"
                title="Manage Models & Providers"
              >
                <Sliders size={12} />
              </button>
            )}
          </div>

          {/* Action Button: Send or Stop */}
          <div className="flex items-center gap-2">
            {isStreaming ? (
              <button
                type="button"
                onClick={onStop}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-rose-600/90 hover:bg-rose-600 text-white text-xs font-medium transition-all shadow-sm shadow-rose-600/30"
                title="Stop generation"
              >
                <Square size={13} fill="currentColor" />
                <span>Stop</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={handleTriggerSend}
                disabled={(!input.trim() && attachedImages.length === 0) || disabled}
                className={`p-2 rounded-xl transition-all flex items-center justify-center ${
                  (input.trim() || attachedImages.length > 0) && !disabled
                    ? 'bg-brand-600 hover:bg-brand-500 text-white shadow-md shadow-brand-600/30'
                    : 'bg-charcoal-800 text-charcoal-600 cursor-not-allowed'
                }`}
                title="Send message"
              >
                <Send size={16} />
              </button>
            )}
          </div>
        </div>
      </div>
      <p className="text-[11px] text-center text-charcoal-500 mt-2">
        AUREVON AI v1.0 • Autonomous Multimodal AI Ecosystem • Multimodal & RAG Enabled
      </p>
    </div>
  );
};
