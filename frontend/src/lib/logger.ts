/**
 * Tiny structured logger for frontend lifecycle events.
 *
 * Centralising logging here means every important event (upload initiated,
 * upload completed, chat request initiated, stream completed, API errors) is
 * emitted in a consistent, greppable format and could later be shipped to a
 * collector. For now it logs to the console.
 */

export type LogEvent =
  | "upload.initiated"
  | "upload.completed"
  | "upload.failed"
  | "chat.request.initiated"
  | "chat.stream.completed"
  | "chat.failed"
  | "api.error";

export function logEvent(event: LogEvent, data: Record<string, unknown> = {}) {
  const entry = { ts: new Date().toISOString(), event, ...data };
  const isError = event.endsWith(".error") || event.endsWith(".failed");
  // eslint-disable-next-line no-console
  (isError ? console.error : console.info)(`[rag] ${event}`, entry);
}
