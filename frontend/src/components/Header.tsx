import { BrainCircuit } from "lucide-react";

export function Header() {
  return (
    <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center gap-3 px-6 py-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-600/20 text-brand-400 ring-1 ring-brand-500/30">
          <BrainCircuit size={20} />
        </div>
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-100">
            RAG Knowledge Assistant
          </h1>
          <p className="text-xs text-slate-400">
            Upload PDFs · ask questions · stream grounded answers
          </p>
        </div>
        <span className="ml-auto rounded-full bg-slate-800 px-3 py-1 text-xs font-medium text-slate-300 ring-1 ring-slate-700">
          Multi-Agent RAG
        </span>
      </div>
    </header>
  );
}
