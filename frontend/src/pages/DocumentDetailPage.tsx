import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getDocument, exportUrl, type DocDetail } from "../api";
import { StatusBadge, ConfidenceBar } from "../ui";

const SEV_STYLES: Record<string, string> = {
  fail: "bg-red-50 text-red-700 border-red-200",
  warning: "bg-amber-50 text-amber-700 border-amber-200",
  pass: "bg-green-50 text-green-700 border-green-200",
  skipped: "bg-gray-50 text-gray-500 border-gray-200",
};

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [doc, setDoc] = useState<DocDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let active = true;
    async function load() {
      try {
        const d = await getDocument(id!);
        if (active) setDoc(d);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "failed");
      }
    }
    load();
    const t = setInterval(() => {
      if (doc && ["completed", "escalated", "rejected", "failed"].includes(doc.status)) return;
      load();
    }, 3000);
    return () => { active = false; clearInterval(t); };
  }, [id, doc?.status]);

  if (error) return <div className="rounded-md bg-red-50 px-4 py-3 text-red-700">{error}</div>;
  if (!doc) return <p className="text-gray-500">Loading…</p>;

  const ext = doc.extraction;
  const results = doc.validation?.report?.results ?? [];
  const problems = results.filter((r) => r.severity === "fail" || r.severity === "warning");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/documents" className="text-sm text-blue-600 hover:underline">← Documents</Link>
          <h1 className="mt-1 text-2xl font-bold">{doc.filename}</h1>
        </div>
        <StatusBadge status={doc.status} />
      </div>

      {ext && (
        <div className="flex gap-2">
          {["json", "csv", "xml", "xlsx"].map((f) => (
            <a key={f} href={exportUrl(id!, f, true)}
               className="rounded-md border px-3 py-1.5 text-sm hover:bg-gray-100">
              Export {f.toUpperCase()}
            </a>
          ))}
        </div>
      )}

      {!ext ? (
        <p className="text-gray-500">Still processing… this page updates automatically.</p>
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          <div className="rounded-lg border bg-white p-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-semibold">Extracted fields</h2>
              {ext.confidence && <ConfidenceBar value={ext.confidence.overall} />}
            </div>
            <table className="w-full text-sm">
              <tbody>
                {ext.confidence?.fields.map((f) => (
                  <tr key={f.field} className="border-b last:border-0">
                    <td className="py-2 pr-4 text-gray-500">{f.field}</td>
                    <td className="py-2 pr-4 font-medium">{String(f.value ?? "—")}</td>
                    <td className="py-2 w-28"><ConfidenceBar value={f.confidence} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="space-y-6">
            <div className="rounded-lg border bg-white p-5">
              <h2 className="mb-3 font-semibold">
                Validation{" "}
                <span className="text-sm font-normal text-gray-500">
                  ({doc.validation?.overall})
                </span>
              </h2>
              {problems.length === 0 ? (
                <p className="text-sm text-green-700">All checks passed.</p>
              ) : (
                <ul className="space-y-2">
                  {problems.map((r, i) => (
                    <li key={i} className={`rounded-md border px-3 py-2 text-sm ${SEV_STYLES[r.severity]}`}>
                      <div className="font-medium">[{r.severity}] {r.rule_id}</div>
                      <div>{r.reason}</div>
                      {r.suggested_fix && <div className="mt-1 text-xs opacity-80">Fix: {r.suggested_fix}</div>}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {doc.review && (
              <div className="rounded-lg border bg-white p-5">
                <h2 className="mb-2 font-semibold">Agent review</h2>
                <div className="mb-2">
                  <span className="rounded-full bg-gray-900 px-2.5 py-0.5 text-xs font-medium text-white">
                    {doc.review.decision}
                  </span>
                  {doc.review.overridden && (
                    <span className="ml-2 text-xs text-amber-600">overridden</span>
                  )}
                </div>
                <p className="text-sm text-gray-600">{doc.review.reasoning}</p>
                {doc.review.override_reason && (
                  <p className="mt-1 text-xs text-amber-600">Override: {doc.review.override_reason}</p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
