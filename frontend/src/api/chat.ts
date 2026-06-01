import { API_BASE_URL } from "../config";
import type { ChatRequest, ChatStreamEvent } from "./types";

/**
 * Stream a RAG answer from POST /chat/stream (Server-Sent Events).
 *
 * Uses fetch + ReadableStream so tokens arrive incrementally. Each parsed
 * event is delivered to onEvent. Pass an AbortSignal to cancel mid-stream.
 */
export async function streamChat(
  req: ChatRequest,
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal,
  });

  if (!resp.ok || !resp.body) {
    throw new Error(`Chat request failed (HTTP ${resp.status}).`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      for (const line of frame.split("\n")) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data:")) continue;
        const payload = trimmed.slice(5).trim();
        if (!payload) continue;
        try {
          onEvent(JSON.parse(payload) as ChatStreamEvent);
        } catch {
          // ignore malformed frame
        }
      }
    }
  }
}
