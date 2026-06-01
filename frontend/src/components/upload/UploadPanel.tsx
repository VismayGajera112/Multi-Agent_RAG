import { FolderUp } from "lucide-react";
import { useDocumentStore } from "../../store/documentStore";
import { UploadDropzone } from "./UploadDropzone";
import { UploadStatusList } from "./UploadStatusList";

export function UploadPanel() {
  const items = useDocumentStore((s) => s.items);
  const addFiles = useDocumentStore((s) => s.addFiles);
  const retry = useDocumentStore((s) => s.retry);
  const remove = useDocumentStore((s) => s.remove);
  const clearCompleted = useDocumentStore((s) => s.clearCompleted);

  const processedCount = items.filter((i) => i.state === "processed").length;
  const activeCount = items.filter(
    (i) => i.state === "uploading" || i.state === "processing",
  ).length;

  return (
    <section
      className="flex h-[70vh] flex-col rounded-2xl border border-slate-800 bg-slate-900/40 p-5 lg:h-full"
      aria-label="Document upload"
    >
      <div className="mb-4 flex items-center gap-2">
        <FolderUp size={18} className="text-brand-400" aria-hidden="true" />
        <h2 className="text-base font-semibold text-slate-100">
          Upload Documents
        </h2>
        <div className="ml-auto flex items-center gap-2 text-xs text-slate-400">
          {activeCount > 0 && (
            <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-amber-300">
              {activeCount} active
            </span>
          )}
          <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-emerald-300">
            {processedCount} ready
          </span>
        </div>
      </div>

      <UploadDropzone onFiles={addFiles} />

      <div className="mb-2 mt-5 flex items-center justify-between">
        <h3 className="text-sm font-medium text-slate-300">
          Document Processing
        </h3>
        {items.length > 0 && (
          <button
            onClick={clearCompleted}
            className="rounded text-xs text-slate-400 hover:text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/60"
          >
            Clear completed
          </button>
        )}
      </div>

      <div className="scroll-area -mr-2 flex-1 overflow-y-auto pr-2">
        <UploadStatusList items={items} onRetry={retry} onRemove={remove} />
      </div>
    </section>
  );
}
