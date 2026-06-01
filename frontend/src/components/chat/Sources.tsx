import { useState } from "react";
import { ChevronDown, ChevronRight, FileText } from "lucide-react";
import type { ChatSource } from "../../api/types";
import { shortId } from "../../lib/format";
import { useDocumentsById } from "../../store/documentStore";

/**
 * Source attribution for an assistant answer.
 *
 * Resolves each retrieved chunk's document_id to its original filename (when
 * the document was uploaded in this session), e.g. "Contract.pdf". Falls back
 * to a short document id otherwise.
 */
export function Sources({ sources }: { sources: ChatSource[] }) {
  const [open, setOpen] = useState(false);
  const docs = useDocumentsById();
  if (!sources.length) return null;

  const label = (s: ChatSource) =>
    (s.document_id && docs[s.document_id]) ||
    `doc ${shortId(s.document_id)}`;

  // Unique filenames for the compact "Sources:" summary line.
  const uniqueNames = Array.from(new Set(sources.map(label)));

  return (
    <div className="mt-2 border-t border-slate-700/60 pt-2">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={`${open ? "Hide" : "Show"} ${sources.length} source${
          sources.length === 1 ? "" : "s"
        }`}
        className="flex items-center gap-1 rounded text-xs font-medium text-slate-400 hover:text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/60"
      >
        {open ? (
          <ChevronDown size={13} aria-hidden="true" />
        ) : (
          <ChevronRight size={13} aria-hidden="true" />
        )}
        Sources ({sources.length})
      </button>

      {!open && (
        <ul className="mt-1.5 flex flex-wrap gap-1.5">
          {uniqueNames.map((name) => (
            <li
              key={name}
              className="inline-flex items-center gap-1 rounded-full bg-slate-900/70 px-2 py-0.5 text-[11px] text-slate-300"
            >
              <FileText size={11} aria-hidden="true" /> {name}
            </li>
          ))}
        </ul>
      )}

      {open && (
        <ul className="mt-2 flex flex-col gap-1.5">
          {sources.map((s, i) => (
            <li
              key={s.id}
              className="rounded-lg bg-slate-900/60 px-2.5 py-1.5 text-xs text-slate-300"
            >
              <div className="mb-0.5 flex items-center gap-1.5 text-slate-400">
                <FileText size={12} aria-hidden="true" />
                <span className="truncate">
                  [{i + 1}] {label(s)} · chunk {s.chunk_index ?? "?"}
                </span>
                <span className="ml-auto shrink-0 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400">
                  {s.score.toFixed(3)}
                </span>
              </div>
              <p className="line-clamp-3 text-slate-400">{s.text}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
