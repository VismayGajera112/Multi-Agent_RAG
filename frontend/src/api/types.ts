// ---- Ingestion (upload) ----
export interface UploadResponse {
  document_id: string;
  task_id: string;
  status: string;
  queue: string;
  filename: string;
  size_bytes: number;
  uploaded_at: string;
  upload_to_queue_ms: number;
  message: string;
}

export type IngestionStatus =
  | "PENDING"
  | "RECEIVED"
  | "STARTED"
  | "RETRY"
  | "SUCCESS"
  | "FAILURE"
  | "DEAD_LETTER"
  | string;

export interface IngestionResult {
  document_id: string;
  chunks_indexed?: number;
  duration_ms?: number;
  collection?: string;
  [key: string]: unknown;
}

export interface IngestionStatusResponse {
  document_id: string;
  task_id?: string | null;
  status: IngestionStatus;
  result?: IngestionResult | null;
  error?: string | null;
}

// ---- Chat ----
export interface ChatSource {
  id: string;
  score: number;
  document_id?: string | null;
  chunk_index?: number | null;
  text: string;
}

export interface ChatRequest {
  query: string;
  top_k?: number;
  collection?: string;
  session_id?: string;
}

export interface ChatResponse {
  session_id: string;
  answer: string;
  sources: ChatSource[];
  retrieval_hits: number;
  prompt_tokens: number;
  completion_tokens: number;
  latency_ms: number;
  provider: string;
}

// ---- Streaming events (SSE) ----
export type ChatStreamEvent =
  | { type: "sources"; session_id: string; sources: ChatSource[] }
  | { type: "token"; text: string }
  | {
      type: "done";
      session_id: string;
      latency_ms: number;
      prompt_tokens: number;
      completion_tokens: number;
      retrieval_hits: number;
      provider: string;
    }
  | { type: "error"; detail: string };
