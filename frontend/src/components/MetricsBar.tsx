import { Activity, AlertTriangle, FileCheck2, Timer } from "lucide-react";
import { useMetricsSummary } from "../store/metricsStore";

/**
 * Compact footer surfacing frontend observability metrics:
 * upload count/failures + avg upload duration, chat request count + avg
 * latency, and API error count. (Detailed events are also logged to console.)
 */
export function MetricsBar() {
  const m = useMetricsSummary();

  const Item = ({
    icon,
    label,
    value,
    tone = "text-slate-300",
  }: {
    icon: React.ReactNode;
    label: string;
    value: string;
    tone?: string;
  }) => (
    <div className="flex items-center gap-1.5">
      <span className="text-slate-500" aria-hidden="true">
        {icon}
      </span>
      <span className="text-slate-500">{label}</span>
      <span className={tone}>{value}</span>
    </div>
  );

  return (
    <footer
      className="flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-slate-800 px-6 py-2 text-[11px] text-slate-400"
      aria-label="Session metrics"
    >
      <span className="font-medium text-slate-500">Session metrics</span>
      <Item
        icon={<FileCheck2 size={12} />}
        label="uploads"
        value={`${m.uploads}`}
      />
      <Item
        icon={<Timer size={12} />}
        label="avg upload"
        value={m.avgUploadMs ? `${(m.avgUploadMs / 1000).toFixed(1)}s` : "—"}
      />
      <Item
        icon={<Activity size={12} />}
        label="chats"
        value={`${m.chatRequests}`}
      />
      <Item
        icon={<Timer size={12} />}
        label="avg latency"
        value={m.avgChatMs ? `${m.avgChatMs} ms` : "—"}
      />
      <Item
        icon={<AlertTriangle size={12} />}
        label="errors"
        value={`${m.uploadFailures + m.apiErrors}`}
        tone={
          m.uploadFailures + m.apiErrors > 0 ? "text-red-300" : "text-slate-300"
        }
      />
    </footer>
  );
}
