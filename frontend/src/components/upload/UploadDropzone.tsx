import { useRef, useState } from "react";
import { UploadCloud } from "lucide-react";
import clsx from "clsx";
import { formatBytes } from "../../lib/format";
import { MAX_FILE_BYTES } from "../../config";

interface Props {
  onFiles: (files: File[]) => void;
}

export function UploadDropzone({ onFiles }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files?.length) {
      onFiles(Array.from(e.dataTransfer.files));
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Upload PDF documents. Activate to choose files, or drag and drop."
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          inputRef.current?.click();
        }
      }}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={clsx(
        "group flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/60",
        dragging
          ? "border-brand-400 bg-brand-500/10"
          : "border-slate-700 bg-slate-900/40 hover:border-brand-500/60 hover:bg-slate-800/40",
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-600/20 text-brand-400 ring-1 ring-brand-500/30">
        <UploadCloud size={24} aria-hidden="true" />
      </div>
      <div>
        <p className="text-sm font-medium text-slate-200">
          Drag &amp; drop PDFs here, or{" "}
          <span className="text-brand-400 underline-offset-2 group-hover:underline">
            choose files
          </span>
        </p>
        <p className="mt-1 text-xs text-slate-500">
          PDF only · up to {formatBytes(MAX_FILE_BYTES)} each · multiple allowed
        </p>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        multiple
        className="hidden"
        onChange={(e) => {
          if (e.target.files?.length) onFiles(Array.from(e.target.files));
          e.target.value = "";
        }}
      />
    </div>
  );
}
