// API base URL. In dev, defaults to "/api" which Vite proxies to the backend
// (no CORS needed). For a static build, set VITE_API_BASE_URL to the API origin.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

// Must mirror the backend's max_upload_bytes (50 MiB).
export const MAX_FILE_BYTES = 50 * 1024 * 1024;

export const ACCEPTED_MIME = ["application/pdf", "application/x-pdf"];
export const ACCEPTED_EXT = [".pdf"];

// How often to poll ingestion status (ms) and for how long before giving up.
export const STATUS_POLL_INTERVAL_MS = 2000;
export const STATUS_POLL_TIMEOUT_MS = 5 * 60 * 1000;
