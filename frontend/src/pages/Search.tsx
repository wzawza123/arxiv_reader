import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArxivApi, type ArxivCandidate } from "../api/client";

export default function Search() {
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const [candidates, setCandidates] = useState<ArxivCandidate[] | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [searchError, setSearchError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<{
    imported: number[];
    skipped: string[];
  } | null>(null);

  const searchMut = useMutation({
    mutationFn: () => ArxivApi.search(query.trim()),
    onSuccess: (data) => {
      setCandidates(data);
      setSelected(new Set());
      setImportResult(null);
      setSearchError(null);
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setSearchError(msg ?? "搜索失败，请稍后重试。");
    },
  });

  const importMut = useMutation({
    mutationFn: () => ArxivApi.import(Array.from(selected)),
    onSuccess: (data) => {
      setImportResult(data);
      setCandidates((prev) =>
        prev
          ? prev.map((c) =>
              data.imported.length > 0 && selected.has(c.arxiv_id) && !c.already_imported
                ? { ...c, already_imported: true }
                : c,
            )
          : prev,
      );
      setSelected(new Set());
      qc.invalidateQueries({ queryKey: ["counts"] });
      qc.invalidateQueries({ queryKey: ["papers"] });
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setSearchError(msg ?? "导入失败，请稍后重试。");
    },
  });

  const toggleAll = () => {
    const importable = (candidates ?? [])
      .filter((c) => !c.already_imported)
      .map((c) => c.arxiv_id);
    if (importable.every((id) => selected.has(id))) {
      setSelected(new Set());
    } else {
      setSelected(new Set(importable));
    }
  };

  const toggle = (arxiv_id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(arxiv_id)) next.delete(arxiv_id);
      else next.add(arxiv_id);
      return next;
    });
  };

  const importable = (candidates ?? []).filter((c) => !c.already_imported);
  const allSelected = importable.length > 0 && importable.every((c) => selected.has(c.arxiv_id));

  return (
    <section className="space-y-4">
      <h2 className="text-xl font-semibold">搜索并归档 arXiv 论文</h2>

      <div className="bg-white border rounded p-4">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (query.trim()) {
              searchMut.mutate();
            }
          }}
        >
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入标题关键词或 arXiv ID（如 2401.12345）"
            className="flex-1 border rounded px-3 py-1.5 text-sm"
          />
          <button
            type="submit"
            disabled={!query.trim() || searchMut.isPending}
            className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm disabled:opacity-50"
          >
            {searchMut.isPending ? "搜索中..." : "搜索"}
          </button>
        </form>
        {searchError && <p className="text-xs text-rose-600 mt-2">{searchError}</p>}
      </div>

      {candidates !== null && (
        <div className="bg-white border rounded">
          <div className="flex items-center justify-between px-4 py-3 border-b">
            <div className="flex items-center gap-3 text-sm">
              <label className="flex items-center gap-1.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={allSelected}
                  disabled={importable.length === 0}
                  onChange={toggleAll}
                />
                <span>全选可导入</span>
              </label>
              <span className="text-slate-400">|</span>
              <span className="text-slate-500">
                找到 {candidates.length} 条，已选 {selected.size} 条
              </span>
            </div>
            <button
              disabled={selected.size === 0 || importMut.isPending}
              onClick={() => importMut.mutate()}
              className="bg-slate-800 text-white px-3 py-1.5 rounded text-sm disabled:opacity-50"
            >
              {importMut.isPending ? "归档中..." : `归档所选 (${selected.size})`}
            </button>
          </div>

          {importResult && (
            <div className="px-4 py-2 text-xs bg-emerald-50 border-b text-emerald-700">
              已导入 {importResult.imported.length} 篇
              {importResult.skipped.length > 0 &&
                `，${importResult.skipped.length} 篇已存在（跳过）`}
            </div>
          )}

          {candidates.length === 0 ? (
            <div className="px-4 py-8 text-center text-slate-400 text-sm">未找到结果</div>
          ) : (
            <ul className="divide-y">
              {candidates.map((c) => (
                <li
                  key={c.arxiv_id}
                  className={`px-4 py-3 flex gap-3 ${c.already_imported ? "opacity-60" : ""}`}
                >
                  <div className="pt-0.5">
                    <input
                      type="checkbox"
                      disabled={c.already_imported}
                      checked={selected.has(c.arxiv_id)}
                      onChange={() => toggle(c.arxiv_id)}
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start gap-2 flex-wrap">
                      <span className="font-medium text-sm leading-snug">{c.title}</span>
                      {c.already_imported && (
                        <span className="text-xs bg-emerald-100 text-emerald-700 rounded px-1.5 py-0.5 shrink-0">
                          {c.paper_id ? (
                            <Link to={`/papers/${c.paper_id}`} className="hover:underline">
                              已归档
                            </Link>
                          ) : (
                            "已归档"
                          )}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      {c.authors.slice(0, 4).join(", ")}
                      {c.authors.length > 4 && " 等"}
                      <span className="mx-1.5">·</span>
                      {c.published_at.slice(0, 10)}
                      <span className="mx-1.5">·</span>
                      {c.categories.join(", ")}
                    </div>
                    <p className="text-xs text-slate-600 mt-1 line-clamp-2">{c.abstract}</p>
                    <a
                      href={c.abs_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-blue-600 hover:underline mt-0.5 inline-block"
                    >
                      {c.arxiv_id}
                    </a>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
