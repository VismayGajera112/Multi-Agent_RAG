import { api } from "./client";
import type { IngestionStatusResponse, UploadResponse } from "./types";

/** Upload a single PDF; reports progress 0..100 via onProgress. */
export async function uploadPdf(
  file: File,
  onProgress?: (percent: number) => void,
  signal?: AbortSignal,
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file, file.name);

  const { data } = await api.post<UploadResponse>("/ingest/upload", form, {
    signal,
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    },
  });
  return data;
}

/** Poll the ingestion status for a document. */
export async function getIngestionStatus(
  documentId: string,
  signal?: AbortSignal,
): Promise<IngestionStatusResponse> {
  const { data } = await api.get<IngestionStatusResponse>(
    `/ingest/${documentId}`,
    { signal },
  );
  return data;
}
