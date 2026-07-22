import { Link, NavLink, Route, Routes } from "react-router-dom";
import UploadPage from "./pages/UploadPage";
import DocumentsPage from "./pages/DocumentsPage";
import DocumentDetailPage from "./pages/DocumentDetailPage";
import ReviewQueuePage from "./pages/ReviewQueuePage";

function NavItem({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        `rounded-md px-3 py-2 text-sm font-medium ${
          isActive ? "bg-gray-900 text-white" : "text-gray-600 hover:bg-gray-100"
        }`
      }
    >
      {label}
    </NavLink>
  );
}

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-3">
          <Link to="/" className="text-lg font-bold">DocIntel</Link>
          <nav className="flex gap-1">
            <NavItem to="/" label="Upload" />
            <NavItem to="/documents" label="Documents" />
            <NavItem to="/review" label="Review Queue" />
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/documents/:id" element={<DocumentDetailPage />} />
          <Route path="/review" element={<ReviewQueuePage />} />
        </Routes>
      </main>
    </div>
  );
}
