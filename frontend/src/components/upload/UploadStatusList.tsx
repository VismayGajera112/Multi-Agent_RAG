import {
  CheckCircle2,
  FileText,
  Loader2,
  RotateCcw,
  Trash2,
  XCircle,
} from "lucide-react";
import clsx from "clsx";
import type { DocItem } from "../../store/documentStore";
import { formatBytes } from "../../lib/format";
import { UploadProgress } from "./UploadProgress";

interface Props {
  items: DocItem[];
  onRetry: (id: string) => void;
  onRemove: (id: string) => void;
}

function StatusBadge({ item }: { item: DocItem }) {
  switch (item.state) {
    case "processed":
      return (
        <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-400">
          <CheckCircle2 size={14} aria-hidden="true" /> Indexed
        </span>
      );
    case "failed":
      return (
        <span className="inline-flex items-center gap-1 text-xs font-medium text-red-400">
          <XCircle size={14} aria-hidden="true" /> Failed
        </span>
      );
    case "uploading":
      return (
        <span className="inline-flex items-center gap-1 text-xs font-medium text-brand-400">
          <Loader2 size={14} className="animate-spin" aria-hidden="true" />{" "}
          Uploading… {item.progress}%
        </span>
      );
    case "processing":
      return (
        <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-400">
          <Loader2 size={14} className="animate-spin" aria-hidden="true" />{" "}
          Processing…
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-400">
          Queued
        </span>
      );
  }
}

export function UploadStatusList({ items, onRetry, onRemove }: Props) {
  if (items.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-slate-500">
        No documents yet. Upload PDFs to build the knowledge base.
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-2" aria-label="Uploaded documents">
      {items.map((item) => (
        <li
          key={item.id}
          className="rounded-xl border border-slate-800 bg-slate-900/50 px-3 py-2.5"
        >
          <div className="flex items-center gap-3">
            <FileText
              size={18}
              className={clsx(
                "shrink-0",
                item.state === "failed" ? "text-red-400" : "text-slate-400",
              )}
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <p className="truncate text-sm font-medium text-slate-200">
                  {item.name}
                </p>
                <StatusBadge item={item} />
              </div>
              <p className="text-xs text-slate-500">
                {formatBytes(item.size)}
                {item.chunks != null && item.state === "processed" && (
                  <span className="text-slate-400">
                    {" "}
                    · {item.chunks} chunk{item.chunks === 1 ? "" : "s"} indexed
                  </span>
                )}
              </p>
            </div>
            <div className="flex items-center gap-1">
              {item.state === "failed" && (
                <button
                  title="Retry"
                  aria-label={`Retry upload of ${item.name}`}
                  onClick={() => onRetry(item.id)}
                  className="rounded-md p-1.5 text-slate-400 hover:bg-slate-800 hover:text-brand-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/60"
                >
                  <RotateCcw size={15} aria-hidden="true" />
                </button>
              )}
              <button
                title="Remove"
                aria-label={`Remove ${item.name}`}
                onClick={() => onRemove(item.id)}
                className="rounded-md p-1.5 text-slate-400 hover:bg-slate-800 hover:text-red-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500/60"
              >
                <Trash2 size={15} aria-hidden="true" />
              </button>
            </div>
          </div>

          {item.state === "uploading" && (
            <UploadProgress percent={item.progress} className="mt-2" />
          )}
          {item.state === "failed" && item.error && (
            <p className="mt-1.5 rounded-md bg-red-500/10 px-2 py-1 text-xs text-red-300">
              {item.error}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}
