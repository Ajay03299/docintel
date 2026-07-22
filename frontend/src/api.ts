// All backend calls in one place. The Vite proxy forwards /api -> :8000.

export type DocStatus =
  | "uploaded" | "processing" | "extracted" | "validated"
  | "review" | "completed" | "failed" | "escalated" | "rejected";

export interface DocListItem {
  document_id: string;
  filename: string;
  status: DocStatus;
  created_at: string;
  overall_confidence: number | null;
  validation: string | null;
  review_decision: string | null;
}

export interface DocListResponse {
  total: number; limit: number; offset: number; items: DocListItem[];
}

export interface FieldScore {
  field: string; value: unknown; confidence: number; signals: string[];
}
export interface ValidationResult {
  rule_id: string; severity: string; reason: string;
  suggested_fix: string | null; fields: string[];
}
export interface DocDetail {
  document_id: string;
  status: DocStatus;
  filename: string;
  extraction: {
    method: string; model: string; data: Record<string, unknown>;
    overall_confidence: number | null;
    confidence: { overall: number; strategy: string; fields: FieldScore[] } | null;
    parse_error: string | null;
  } | null;
  validation: { overall: string; report: { results: ValidationResult[] } } | null;
  review: {
    decision: string; reasoning: string; attempts: number;
    overridden: boolean; override_reason: string | null; history: unknown[];
  } | null;
}

const BASE = "/api/v1";

export async function listDocuments(status?: string): Promise<DocListResponse> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  const r = await fetch(`${BASE}/documents${q}`);
  if (!r.ok) throw new Error(`list failed: ${r.status}`);
  return r.json();
}

export async function getDocument(id: string): Promise<DocDetail> {
  const r = await fetch(`${BASE}/documents/${id}`);
  if (!r.ok) throw new Error(`get failed: ${r.status}`);
  return r.json();
}

export async function uploadDocument(file: File): Promise<{ document_id: string }> {
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch(`${BASE}/documents`, { method: "POST", body: fd });
  if (!r.ok) throw new Error(`upload failed: ${r.status}`);
  return r.json();
}

export function exportUrl(id: string, format: string, evidence = false): string {
  return `${BASE}/documents/${id}/export?format=${format}${evidence ? "&include_evidence=true" : ""}`;
}
