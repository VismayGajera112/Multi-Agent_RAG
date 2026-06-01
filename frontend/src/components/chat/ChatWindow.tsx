import { MessageCircle, Trash2 } from "lucide-react";
import { useChatStore } from "../../store/chatStore";
import { ChatInput } from "./ChatInput";
import { MessageList } from "./MessageList";

export function ChatWindow({ hasDocuments }: { hasDocuments: boolean }) {
  const messages = useChatStore((s) => s.messages);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const send = useChatStore((s) => s.send);
  const stop = useChatStore((s) => s.stop);
  const clear = useChatStore((s) => s.clear);

  return (
    <section
      className="flex h-[70vh] flex-col rounded-2xl border border-slate-800 bg-slate-900/40 p-5 lg:h-full"
      aria-label="Chat"
    >
      <div className="mb-4 flex items-center gap-2">
        <MessageCircle size={18} className="text-brand-400" aria-hidden="true" />
        <h2 className="text-base font-semibold text-slate-100">Chat Window</h2>
        {messages.length > 0 && (
          <button
            onClick={clear}
            aria-label="Clear conversation"
            className="ml-auto inline-flex items-center gap-1 rounded text-xs text-slate-400 hover:text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/60"
          >
            <Trash2 size={14} aria-hidden="true" /> Clear
          </button>
        )}
      </div>

      <div className="min-h-0 flex-1">
        <MessageList messages={messages} hasDocuments={hasDocuments} />
      </div>

      <div className="mt-4">
        <ChatInput onSend={send} onStop={stop} isStreaming={isStreaming} />
        <p className="mt-1.5 px-1 text-[11px] text-slate-500">
          Press Enter to send · Shift+Enter for a new line
        </p>
      </div>
    </section>
  );
}
