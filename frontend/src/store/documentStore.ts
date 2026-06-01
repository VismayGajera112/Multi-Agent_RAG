import { create } from "zustand";
import { useShallow } from "zustand/react/shallow";
import { parseApiError } from "../api/client";
import { getIngestionStatus, uploadPdf } from "../api/documents";
import { STATUS_POLL_INTERVAL_MS, STATUS_POLL_TIMEOUT_MS } from "../config";
import { logEvent } from "../lib/logger";
import { validatePdf } from "../lib/validation";
import { useMetricsStore } from "./metricsStore";

export type DocState =
  | "queued"
  | "uploading"
  | "processing"
  | "processed"
  | "failed";

export interface DocItem {
  id: string;
  file: File;
  name: string;
  size: number;
  state: DocState;
  progress: number;
  documentId?: string;
  taskId?: string;
  chunks?: number;
  error?: string;
  startedAt?: number;
}

interface DocumentStore {
  items: DocItem[];
  addFiles: (files: File[] | FileList) => void;
  retry: (id: string) => void;
  remove: (id: string) => void;
  clearCompleted: () => void;
}

const TERMINAL_OK = new Set(["SUCCESS"]);
const TERMINAL_BAD = new Set(["FAILURE", "DEAD_LETTER"]);

const uid = () =>
  globalThis.crypto?.randomUUID?.() ??
  `${Date.now()}-${Math.random().toString(16).slice(2)}`;

// AbortControllers live outside React/Zustand state.
const aborters = new Map<string, AbortController>();

export const useDocumentStore = create<DocumentStore>((set, get) => {
  const patch = (id: string, next: Partial<DocItem>) =>
    set((s) => ({
      items: s.items.map((it) => (it.id === id ? { ...it, ...next } : it)),
    }));

  const pollStatus = async (id: string, documentId: string) => {
    const controller = aborters.get(id) ?? new AbortController();
    aborters.set(id, controller);
    const deadline = Date.now() + STATUS_POLL_TIMEOUT_MS;

    while (Date.now() < deadline && !controller.signal.aborted) {
      try {
        const s = await getIngestionStatus(documentId, controller.signal);
        if (TERMINAL_OK.has(s.status)) {
          patch(id, {
            state: "processed",
            chunks: s.result?.chunks_indexed,
            taskId: s.task_id ?? undefined,
          });
          const item = get().items.find((i) => i.id === id);
          const dur = item?.startedAt ? Date.now() - item.startedAt : 0;
          useMetricsStore.getState().recordUploadCompleted(dur);
          logEvent("upload.completed", {
            name: item?.name,
            documentId,
            durationMs: dur,
            chunks: s.result?.chunks_indexed,
          });
          return;
        }
        if (TERMINAL_BAD.has(s.status)) {
          patch(id, {
            state: "failed",
            error: s.error || `Document processing failed (${s.status}).`,
          });
          useMetricsStore.getState().recordUploadFailed();
          logEvent("upload.failed", { documentId, status: s.status });
          return;
        }
        patch(id, { state: "processing" });
      } catch {
        if (controller.signal.aborted) return;
      }
      await new Promise((r) => setTimeout(r, STATUS_POLL_INTERVAL_MS));
    }
    if (!controller.signal.aborted) {
      patch(id, {
        state: "failed",
        error: "Timed out waiting for processing to complete.",
      });
      useMetricsStore.getState().recordUploadFailed();
    }
  };

  const startUpload = async (id: string) => {
    const item = get().items.find((it) => it.id === id);
    if (!item) return;

    const controller = new AbortController();
    aborters.set(id, controller);
    const startedAt = Date.now();
    patch(id, { state: "uploading", progress: 0, error: undefined, startedAt });
    useMetricsStore.getState().recordUploadInitiated();
    logEvent("upload.initiated", { name: item.name, size: item.size });

    try {
      const res = await uploadPdf(
        item.file,
        (p) => patch(id, { progress: p }),
        controller.signal,
      );
      patch(id, {
        state: "processing",
        progress: 100,
        documentId: res.document_id,
        taskId: res.task_id,
      });
      await pollStatus(id, res.document_id);
    } catch (err) {
      if (controller.signal.aborted) return;
      const msg = parseApiError(err);
      patch(id, { state: "failed", error: msg });
      useMetricsStore.getState().recordUploadFailed();
      useMetricsStore.getState().recordApiError();
      logEvent("upload.failed", { name: item.name, error: msg });
    }
  };

  return {
    items: [],

    addFiles: (files) => {
      const created: DocItem[] = Array.from(files).map((file) => {
        const v = validatePdf(file);
        return {
          id: uid(),
          file,
          name: file.name,
          size: file.size,
          state: v.ok ? "queued" : "failed",
          progress: 0,
          error: v.ok ? undefined : v.reason,
        };
      });
      set((s) => ({ items: [...s.items, ...created] }));
      created
        .filter((c) => c.state === "queued")
        .forEach((c) => void startUpload(c.id));
    },

    retry: (id) => {
      patch(id, { state: "queued", progress: 0, error: undefined });
      void startUpload(id);
    },

    remove: (id) => {
      aborters.get(id)?.abort();
      aborters.delete(id);
      set((s) => ({ items: s.items.filter((it) => it.id !== id) }));
    },

    clearCompleted: () =>
      set((s) => ({
        items: s.items.filter(
          (it) => it.state !== "processed" && it.state !== "failed",
        ),
      })),
  };
});

/** Map of documentId -> filename, for resolving chat source citations. */
export function useDocumentsById(): Record<string, string> {
  return useDocumentStore(
    useShallow((s) => {
      const map: Record<string, string> = {};
      for (const it of s.items) {
        if (it.documentId) map[it.documentId] = it.name;
      }
      return map;
    }),
  );
}
