import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listDocuments, type DocListItem } from "../api";
import { StatusBadge, ConfidenceBar } from "../ui";

export default function ReviewQueuePage() {
  const [items, setItems] = useState<DocListItem[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    const res = await listDocuments("escalated");
    setItems(res.items);
    setLoading(false);
  }
  useEffect(() => { load(); const t = setInterval(load, 4000); return () => clearInterval(t); }, []);

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Review Queue</h1>
      <p className="mb-4 text-sm text-gray-500">
        Documents the agent escalated for human review — low confidence or failed validation.
      </p>
      {loading ? (
        <p className="text-gray-500">Loading…</p>
      ) : items.length === 0 ? (
        <p className="rounded-lg border bg-white px-4 py-8 text-center text-gray-500">
          Nothing to review.
        </p>
      ) : (
        <div className="space-y-3">
          {items.map((d) => (
            <Link key={d.document_id} to={`/documents/${d.document_id}`}
                  className="flex items-center justify-between rounded-lg border bg-white px-5 py-4 hover:bg-gray-50">
              <div>
                <div className="font-medium">{d.filename}</div>
                <div className="text-xs text-gray-500">{new Date(d.created_at).toLocaleString()}</div>
              </div>
              <div className="flex items-center gap-4">
                <ConfidenceBar value={d.overall_confidence} />
                <StatusBadge status={d.status} />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
