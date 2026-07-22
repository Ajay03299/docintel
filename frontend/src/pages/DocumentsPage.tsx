import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listDocuments, type DocListItem } from "../api";
import { StatusBadge, ConfidenceBar } from "../ui";

export default function DocumentsPage() {
  const [items, setItems] = useState<DocListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setError(null);
      const res = await listDocuments();
      setItems(res.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Documents</h1>
        <button onClick={load} className="rounded-md border px-3 py-1.5 text-sm hover:bg-gray-100">
          Refresh
        </button>
      </div>

      {error && <div className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {loading ? (
        <p className="text-gray-500">Loading…</p>
      ) : items.length === 0 ? (
        <p className="text-gray-500">No documents yet. Upload one to get started.</p>
      ) : (
        <div className="overflow-hidden rounded-lg border bg-white">
          <table className="w-full text-sm">
            <thead className="border-b bg-gray-50 text-left text-gray-500">
              <tr>
                <th className="px-4 py-2 font-medium">File</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Confidence</th>
                <th className="px-4 py-2 font-medium">Validation</th>
                <th className="px-4 py-2 font-medium">Review</th>
              </tr>
            </thead>
            <tbody>
              {items.map((d) => (
                <tr key={d.document_id} className="border-b last:border-0 hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link to={`/documents/${d.document_id}`} className="font-medium text-blue-600 hover:underline">
                      {d.filename}
                    </Link>
                  </td>
                  <td className="px-4 py-3"><StatusBadge status={d.status} /></td>
                  <td className="px-4 py-3"><ConfidenceBar value={d.overall_confidence} /></td>
                  <td className="px-4 py-3 text-gray-600">{d.validation ?? "—"}</td>
                  <td className="px-4 py-3 text-gray-600">{d.review_decision ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
