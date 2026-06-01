import clsx from "clsx";
import { Bot, User } from "lucide-react";
import type { ChatMessage } from "../../store/chatStore";
import { Sources } from "./Sources";

/** Renders a finalized (non-streaming) chat message — user or assistant. */
export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div
      className={clsx("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}
      role="listitem"
    >
      <div
        className={clsx(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full ring-1",
          isUser
            ? "bg-brand-600/20 text-brand-300 ring-brand-500/30"
            : "bg-slate-800 text-slate-300 ring-slate-700",
        )}
      >
        {isUser ? (
          <User size={16} aria-hidden="true" />
        ) : (
          <Bot size={16} aria-hidden="true" />
        )}
      </div>

      <div
        className={clsx(
          "max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
          isUser
            ? "bg-brand-600 text-white"
            : message.error
              ? "bg-red-500/10 text-red-200 ring-1 ring-red-500/30"
              : "bg-slate-800/80 text-slate-100 ring-1 ring-slate-700/60",
        )}
      >
        <span className="sr-only">{isUser ? "You said: " : "Assistant: "}</span>
        <div className="whitespace-pre-wrap break-words">{message.content}</div>

        {!isUser && message.sources && message.sources.length > 0 && (
          <Sources sources={message.sources} />
        )}

        {!isUser && message.meta && (
          <div className="mt-1.5 text-[11px] text-slate-400">
            {message.meta.provider} · {message.meta.tokens} tokens ·{" "}
            {Math.round(message.meta.latencyMs)} ms
          </div>
        )}
      </div>
    </div>
  );
}
