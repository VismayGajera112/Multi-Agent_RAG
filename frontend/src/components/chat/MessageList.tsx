import { useEffect, useRef } from "react";
import { MessagesSquare } from "lucide-react";
import type { ChatMessage } from "../../store/chatStore";
import { MessageBubble } from "./MessageBubble";
import { StreamingMessage } from "./StreamingMessage";

interface Props {
  messages: ChatMessage[];
  hasDocuments: boolean;
}

export function MessageList({ messages, hasDocuments }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the newest content (including each streamed token).
  const streamingLen = messages[messages.length - 1]?.content.length ?? 0;
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, streamingLen]);

  if (messages.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-slate-500">
        <MessagesSquare size={32} className="text-slate-600" aria-hidden="true" />
        <div>
          <p className="text-sm font-medium text-slate-400">
            Ask anything about your documents
          </p>
          <p className="mt-1 text-xs">
            {hasDocuments
              ? "Your knowledge base is ready — try a question below."
              : "Upload a PDF on the left to ground answers in your own data."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="scroll-area flex flex-col gap-4 overflow-y-auto pr-1"
      role="log"
      aria-label="Conversation history"
      aria-live="polite"
    >
      {messages.map((m) =>
        m.role === "assistant" && m.streaming ? (
          <StreamingMessage key={m.id} message={m} />
        ) : (
          <MessageBubble key={m.id} message={m} />
        ),
      )}
      <div ref={bottomRef} />
    </div>
  );
}
