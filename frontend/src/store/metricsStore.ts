import { create } from "zustand";
import { useShallow } from "zustand/react/shallow";

/**
 * Frontend observability metrics.
 *
 * Captures upload duration, upload failures, chat request latency, and stream
 * completion time — surfaced in a small footer bar and logged to the console.
 */
interface MetricsState {
  uploadsInitiated: number;
  uploadsCompleted: number;
  uploadFailures: number;
  uploadDurationsMs: number[];

  chatRequests: number;
  chatLatenciesMs: number[];
  streamCompletionsMs: number[];

  apiErrors: number;

  recordUploadInitiated: () => void;
  recordUploadCompleted: (durationMs: number) => void;
  recordUploadFailed: () => void;
  recordChatInitiated: () => void;
  recordChatLatency: (ms: number) => void;
  recordStreamCompletion: (ms: number) => void;
  recordApiError: () => void;
}

const avg = (xs: number[]) =>
  xs.length ? Math.round(xs.reduce((a, b) => a + b, 0) / xs.length) : 0;

export const useMetricsStore = create<MetricsState>((set) => ({
  uploadsInitiated: 0,
  uploadsCompleted: 0,
  uploadFailures: 0,
  uploadDurationsMs: [],
  chatRequests: 0,
  chatLatenciesMs: [],
  streamCompletionsMs: [],
  apiErrors: 0,

  recordUploadInitiated: () =>
    set((s) => ({ uploadsInitiated: s.uploadsInitiated + 1 })),
  recordUploadCompleted: (durationMs) =>
    set((s) => ({
      uploadsCompleted: s.uploadsCompleted + 1,
      uploadDurationsMs: [...s.uploadDurationsMs, durationMs],
    })),
  recordUploadFailed: () => set((s) => ({ uploadFailures: s.uploadFailures + 1 })),
  recordChatInitiated: () => set((s) => ({ chatRequests: s.chatRequests + 1 })),
  recordChatLatency: (ms) =>
    set((s) => ({ chatLatenciesMs: [...s.chatLatenciesMs, ms] })),
  recordStreamCompletion: (ms) =>
    set((s) => ({ streamCompletionsMs: [...s.streamCompletionsMs, ms] })),
  recordApiError: () => set((s) => ({ apiErrors: s.apiErrors + 1 })),
}));

/** Derived, display-friendly metric summary. */
export function useMetricsSummary() {
  return useMetricsStore(
    useShallow((s) => ({
      uploads: s.uploadsCompleted,
      uploadFailures: s.uploadFailures,
      avgUploadMs: avg(s.uploadDurationsMs),
      chatRequests: s.chatRequests,
      avgChatMs: avg(s.chatLatenciesMs),
      apiErrors: s.apiErrors,
    })),
  );
}
