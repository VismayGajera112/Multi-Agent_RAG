import { useState } from "react";
import { Send, Square } from "lucide-react";

interface Props {
  onSend: (text: string) => void;
  onStop: () => void;
  isStreaming: boolean;
}

export function ChatInput({ onSend, onStop, isStreaming }: Props) {
  const [text, setText] = useState("");

  const submit = () => {
    const value = text.trim();
    if (!value || isStreaming) return;
    onSend(value);
    setText("");
  };

  return (
    <div className="flex items-end gap-2 rounded-2xl border border-slate-700 bg-slate-900/70 p-2 focus-within:border-brand-500/60">
      <label htmlFor="chat-input" className="sr-only">
        Ask a question about your documents
      </label>
      <textarea
        id="chat-input"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        rows={1}
        placeholder="Ask a question about your documents…"
        aria-label="Chat message"
        className="max-h-32 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none"
      />
      {isStreaming ? (
        <button
          onClick={onStop}
          aria-label="Stop generating"
          title="Stop"
          className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-700 text-slate-200 hover:bg-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/60"
        >
          <Square size={16} aria-hidden="true" />
        </button>
      ) : (
        <button
          onClick={submit}
          disabled={!text.trim()}
          aria-label="Send message"
          title="Send"
          className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-600 text-white transition hover:bg-brand-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Send size={16} aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
