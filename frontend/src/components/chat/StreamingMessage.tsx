import { Bot } from "lucide-react";
import type { ChatMessage } from "../../store/chatStore";
import { Sources } from "./Sources";
import { TypingIndicator } from "./TypingIndicator";

/**
 * Renders the assistant message that is currently streaming.
 *
 * Before the first token arrives it shows a TypingIndicator ("Assistant is
 * thinking…"); once tokens stream in, the text updates live with a blinking
 * cursor. The content region is an aria-live polite region so assistive tech
 * announces incremental updates.
 */
export function StreamingMessage({ message }: { message: ChatMessage }) {
  const hasText = message.content.length > 0;

  return (
    <div className="flex flex-row gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-800 text-slate-300 ring-1 ring-slate-700">
        <Bot size={16} aria-hidden="true" />
      </div>

      <div className="max-w-[80%] rounded-2xl bg-slate-800/80 px-4 py-2.5 text-sm leading-relaxed text-slate-100 ring-1 ring-slate-700/60">
        <div aria-live="polite" aria-busy="true">
          {hasText ? (
            <span className="whitespace-pre-wrap break-words">
              {message.content}
              <span className="cursor-blink" aria-hidden="true" />
            </span>
          ) : (
            <TypingIndicator />
          )}
        </div>

        {message.sources && message.sources.length > 0 && (
          <Sources sources={message.sources} />
        )}
      </div>
    </div>
  );
}
