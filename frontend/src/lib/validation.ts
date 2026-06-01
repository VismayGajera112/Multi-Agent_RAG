import { ACCEPTED_EXT, ACCEPTED_MIME, MAX_FILE_BYTES } from "../config";
import { formatBytes } from "./format";

export interface ValidationResult {
  ok: boolean;
  reason?: string;
}

export function validatePdf(file: File): ValidationResult {
  const nameOk = ACCEPTED_EXT.some((ext) =>
    file.name.toLowerCase().endsWith(ext),
  );
  // Some browsers report an empty MIME type for PDFs; accept name-based match.
  const typeOk = ACCEPTED_MIME.includes(file.type) || file.type === "";

  if (!nameOk && !typeOk) {
    return { ok: false, reason: "Unsupported file type — PDFs only." };
  }
  if (file.size === 0) {
    return { ok: false, reason: "File is empty." };
  }
  if (file.size > MAX_FILE_BYTES) {
    return {
      ok: false,
      reason: `Too large (max ${formatBytes(MAX_FILE_BYTES)}).`,
    };
  }
  return { ok: true };
}
