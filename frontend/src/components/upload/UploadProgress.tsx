import clsx from "clsx";

interface Props {
  percent: number;
  className?: string;
  tone?: "brand" | "green" | "red";
}

export function UploadProgress({ percent, className, tone = "brand" }: Props) {
  const bar =
    tone === "green"
      ? "bg-emerald-500"
      : tone === "red"
        ? "bg-red-500"
        : "bg-brand-500";
  return (
    <div
      className={clsx(
        "h-1.5 w-full overflow-hidden rounded-full bg-slate-700/70",
        className,
      )}
    >
      <div
        className={clsx("h-full rounded-full transition-all duration-300", bar)}
        style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
      />
    </div>
  );
}
