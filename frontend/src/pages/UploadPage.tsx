import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { uploadDocument } from "../api";

export default function UploadPage() {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nav = useNavigate();

  async function handleFile(file: File) {
    setError(null);
    setUploading(true);
    try {
      const { document_id } = await uploadDocument(file);
      nav(`/documents/${document_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="mb-1 text-2xl font-bold">Upload a document</h1>
      <p className="mb-6 text-sm text-gray-500">
        PDF, PNG or JPEG. Processing runs asynchronously — you'll be taken to the
        document's status page.
      </p>

      <label
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const f = e.dataTransfer.files?.[0];
          if (f) handleFile(f);
        }}
        className={`flex h-56 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed transition ${
          dragging ? "border-gray-900 bg-gray-100" : "border-gray-300 bg-white"
        }`}
      >
        <input
          type="file"
          accept=".pdf,.png,.jpg,.jpeg"
          className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
        />
        {uploading ? (
          <span className="text-gray-500">Uploading…</span>
        ) : (
          <>
            <span className="text-4xl">📄</span>
            <span className="mt-2 font-medium">Drop a file here, or click to browse</span>
          </>
        )}
      </label>

      {error && (
        <div className="mt-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
    </div>
  );
}
