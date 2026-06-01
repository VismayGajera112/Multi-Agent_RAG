/** Animated "Assistant is thinking…" indicator shown before the first token. */
export function TypingIndicator() {
  return (
    <span
      className="inline-flex items-center gap-2 text-slate-400"
      role="status"
      aria-label="Assistant is thinking"
    >
      <span className="flex gap-1" aria-hidden="true">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </span>
      <span className="text-xs">Assistant is thinking…</span>
    </span>
  );
}
