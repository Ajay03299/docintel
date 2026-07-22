import type { DocStatus } from "./api";

const STATUS_STYLES: Record<string, string> = {
  completed: "bg-green-100 text-green-800",
  escalated: "bg-amber-100 text-amber-800",
  rejected: "bg-red-100 text-red-800",
  failed: "bg-red-100 text-red-800",
  processing: "bg-blue-100 text-blue-800",
  review: "bg-purple-100 text-purple-800",
  uploaded: "bg-gray-100 text-gray-700",
};

export function StatusBadge({ status }: { status: DocStatus | string }) {
  const cls = STATUS_STYLES[status] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}

export function ConfidenceBar({ value }: { value: number | null }) {
  if (value == null) return <span className="text-gray-400">—</span>;
  const pct = Math.round(value * 100);
  const color = value >= 0.7 ? "bg-green-500" : value >= 0.4 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-20 rounded-full bg-gray-200">
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-600">{pct}%</span>
    </div>
  );
}
