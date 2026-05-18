import { Link, NavLink, Route, Routes } from "react-router-dom";
import Inbox from "./pages/Inbox";
import ToRead from "./pages/ToRead";
import Read from "./pages/Read";
import NotInterested from "./pages/NotInterested";
import Settings from "./pages/Settings";
import PaperDetail from "./pages/PaperDetail";
import Jobs from "./pages/Jobs";
import Search from "./pages/Search";
import { useQuery } from "@tanstack/react-query";
import { PaperApi } from "./api/client";

function NavItem({
  to,
  label,
  count,
}: {
  to: string;
  label: string;
  count?: number;
}) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        `px-3 py-1.5 rounded text-sm ${
          isActive
            ? "bg-slate-900 text-white"
            : "text-slate-700 hover:bg-slate-200"
        }`
      }
    >
      {label}
      {count !== undefined && (
        <span className="ml-1.5 text-xs opacity-70">({count})</span>
      )}
    </NavLink>
  );
}

export default function App() {
  const { data: counts } = useQuery({
    queryKey: ["counts"],
    queryFn: PaperApi.counts,
    refetchInterval: 30_000,
  });

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b bg-white sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-4">
          <Link to="/" className="font-semibold text-lg text-slate-800">
            arXiv Daily Reader
          </Link>
          <nav className="flex gap-1 ml-2">
            <NavItem to="/" label="Inbox" count={counts?.new} />
            <NavItem to="/to-read" label="待阅读" count={counts?.to_read} />
            <NavItem to="/read" label="已读" count={counts?.read} />
            <NavItem
              to="/not-interested"
              label="不感兴趣"
              count={counts?.not_interested}
            />
            <NavItem to="/jobs" label="任务" />
            <NavItem to="/search" label="搜索归档" />
            <NavItem to="/settings" label="设置" />
          </nav>
        </div>
      </header>
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-6">
        <Routes>
          <Route path="/" element={<Inbox />} />
          <Route path="/to-read" element={<ToRead />} />
          <Route path="/read" element={<Read />} />
          <Route path="/not-interested" element={<NotInterested />} />
          <Route path="/jobs" element={<Jobs />} />
          <Route path="/search" element={<Search />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/papers/:id" element={<PaperDetail />} />
        </Routes>
      </main>
    </div>
  );
}
