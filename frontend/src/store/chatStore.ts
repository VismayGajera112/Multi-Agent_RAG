import { create } from "zustand";
import { streamChat } from "../api/chat";
import type { ChatSource } from "../api/types";
import { logEvent } from "../lib/logger";
import { useMetricsStore } from "./metricsStore";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  streaming?: boolean;
  error?: boolean;
  meta?: { latencyMs: number; tokens: number; provider: string };
}

interface ChatStore {
  messages: ChatMessage[];
  isStreaming: boolean;
  sessionId: string;
  send: (query: string) => Promise<void>;
  stop: () => void;
  clear: () => void;
}

const uid = () =>
  globalThis.crypto?.randomUUID?.() ??
  `${Date.now()}-${Math.random().toString(16).slice(2)}`;

let aborter: AbortController | null = null;

export const useChatStore = create<ChatStore>((set, get) => {
  const update = (id: string, fn: (m: ChatMessage) => ChatMessage) =>
    set((s) => ({ messages: s.messages.map((m) => (m.id === id ? fn(m) : m)) }));

  return {
    messages: [],
    isStreaming: false,
    sessionId: uid(),

    send: async (query) => {
      const text = query.trim();
      if (!text || get().isStreaming) return;

      const assistantId = uid();
      set((s) => ({
        messages: [
          ...s.messages,
          { id: uid(), role: "user", content: text },
          { id: assistantId, role: "assistant", content: "", streaming: true },
        ],
        isStreaming: true,
      }));

      const metrics = useMetricsStore.getState();
      metrics.recordChatInitiated();
      logEvent("chat.request.initiated", { query: text });

      const controller = new AbortController();
      aborter = controller;
      const startedAt = performance.now();
      let firstTokenLogged = false;

      try {
        await streamChat(
          { query: text, session_id: get().sessionId },
          (evt) => {
            if (evt.type === "sources") {
              update(assistantId, (m) => ({ ...m, sources: evt.sources }));
            } else if (evt.type === "token") {
              if (!firstTokenLogged) {
                firstTokenLogged = true;
                metrics.recordChatLatency(performance.now() - startedAt);
              }
              update(assistantId, (m) => ({
                ...m,
                content: m.content + evt.text,
              }));
            } else if (evt.type === "done") {
              const total = performance.now() - startedAt;
              metrics.recordStreamCompletion(total);
              logEvent("chat.stream.completed", {
                serverLatencyMs: evt.latency_ms,
                clientTotalMs: Math.round(total),
                tokens: evt.prompt_tokens + evt.completion_tokens,
                provider: evt.provider,
              });
              update(assistantId, (m) => ({
                ...m,
                streaming: false,
                meta: {
                  latencyMs: evt.latency_ms,
                  tokens: evt.prompt_tokens + evt.completion_tokens,
                  provider: evt.provider,
                },
              }));
            } else if (evt.type === "error") {
              update(assistantId, (m) => ({
                ...m,
                streaming: false,
                error: true,
                content: m.content || `⚠️ ${evt.detail}`,
              }));
            }
          },
          controller.signal,
        );
      } catch (err) {
        if (!controller.signal.aborted) {
          const msg =
            err instanceof Error ? err.message : "Chat request failed.";
          useMetricsStore.getState().recordApiError();
          logEvent("chat.failed", { error: msg });
          update(assistantId, (m) => ({
            ...m,
            streaming: false,
            error: true,
            content:
              m.content ||
              "⚠️ Unable to reach the API. Please check your connection and retry.",
          }));
        }
      } finally {
        update(assistantId, (m) => ({ ...m, streaming: false }));
        set({ isStreaming: false });
        aborter = null;
      }
    },

    stop: () => {
      aborter?.abort();
      set({ isStreaming: false });
    },

    clear: () => {
      aborter?.abort();
      set({ messages: [], sessionId: uid() });
    },
  };
});
