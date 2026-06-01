import axios, { AxiosError } from "axios";
import { API_BASE_URL } from "../config";

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60_000,
});

/** Normalise any axios/network error into a human-readable message. */
export function parseApiError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const e = err as AxiosError<{ detail?: string }>;

    if (e.code === "ERR_NETWORK") {
      return "Cannot reach the API. Is the backend running?";
    }
    if (e.code === "ECONNABORTED") {
      return "The request timed out. Please try again.";
    }
    if (e.response) {
      const { status, data } = e.response;
      const detail =
        (data && typeof data === "object" && data.detail) || undefined;
      switch (status) {
        case 413:
          return detail || "File is too large.";
        case 415:
          return detail || "Unsupported file type — only PDFs are accepted.";
        case 422:
          return detail || "Invalid request.";
        case 503:
          return detail || "Service is temporarily unavailable. Retry shortly.";
        default:
          return detail || `Request failed (HTTP ${status}).`;
      }
    }
  }
  if (err instanceof Error) return err.message;
  return "An unexpected error occurred.";
}
