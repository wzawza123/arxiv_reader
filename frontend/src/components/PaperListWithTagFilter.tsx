import { useMemo, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { PaperApi, TagApi, type PaperListItem } from "../api/client";
import PaperCard from "./PaperCard";

type PaperStatus = PaperListItem["status"];

type Props = {
  title: string;
  description?: ReactNode;
  emptyText: string;
  status: PaperStatus;
  refetchInterval?: number;
};

export default function PaperListWithTagFilter({
  title,
  description,
  emptyText,
  status,
  refetchInterval,
}: Props) {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedTag = searchParams.get("tag")?.trim() ?? "";

  const papersQuery = useQuery({
    queryKey: ["papers", status, { tag: selectedTag }],
    queryFn: () =>
      PaperApi.list({ status, tag: selectedTag ? selectedTag : undefined }),
    refetchInterval,
  });

  const tagsQuery = useQuery({
    queryKey: ["tags"],
    queryFn: TagApi.list,
    refetchInterval: 30_000,
  });

  const selectTag = (tagName: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (tagName) {
      next.set("tag", tagName);
    } else {
      next.delete("tag");
    }
    setSearchParams(next);
  };

  const papers = papersQuery.data ?? [];
  const visibleTags = useMemo(
    () =>
      (tagsQuery.data ?? [])
        .filter((tag) => (tag.paper_count ?? 0) > 0)
        .sort((a, b) => {
          const countDiff = (b.paper_count ?? 0) - (a.paper_count ?? 0);
          return countDiff || a.name.localeCompare(b.name);
        }),
    [tagsQuery.data],
  );

  return (
    <div className="flex flex-col gap-5 md:flex-row md:items-start">
      <aside className="w-full shrink-0 md:w-56 lg:w-64">
        <div className="sticky top-20 rounded-lg border bg-white p-3 shadow-sm">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-slate-800">标签</h3>
            {selectedTag && (
              <button
                type="button"
                onClick={() => selectTag(null)}
                className="text-xs text-slate-500 hover:text-slate-900"
              >
                清除
              </button>
            )}
          </div>

          <button
            type="button"
            onClick={() => selectTag(null)}
            className={`mb-1 flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-sm ${
              selectedTag
                ? "text-slate-600 hover:bg-slate-100"
                : "bg-slate-900 text-white"
            }`}
          >
            <span>全部</span>
            <span className="text-xs opacity-70">
              {visibleTags.reduce((sum, tag) => sum + (tag.paper_count ?? 0), 0)}
            </span>
          </button>

          {tagsQuery.isLoading && (
            <p className="px-2 py-2 text-sm text-slate-500">加载中...</p>
          )}
          {!tagsQuery.isLoading && visibleTags.length === 0 && (
            <p className="px-2 py-2 text-sm text-slate-500">暂无标签</p>
          )}
          <div className="max-h-[calc(100vh-12rem)] overflow-y-auto pr-1">
            {visibleTags.map((tag) => {
              const isActive = selectedTag === tag.name;
              return (
                <button
                  key={tag.id}
                  type="button"
                  title={tag.description ?? undefined}
                  onClick={() => selectTag(tag.name)}
                  className={`mb-1 flex w-full items-center justify-between gap-2 rounded px-2 py-1.5 text-left text-sm ${
                    isActive
                      ? "bg-blue-600 text-white"
                      : "text-slate-700 hover:bg-slate-100"
                  }`}
                >
                  <span className="min-w-0 truncate">{tag.name}</span>
                  <span
                    className={`shrink-0 rounded px-1.5 py-0.5 text-xs ${
                      isActive
                        ? "bg-blue-500 text-white"
                        : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {tag.paper_count ?? 0}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </aside>

      <section className="min-w-0 flex-1">
        <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-xl font-semibold">{title}</h2>
            {description}
          </div>
          {selectedTag && (
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span>
                当前标签:
                <span className="ml-1 font-medium text-slate-800">
                  {selectedTag}
                </span>
              </span>
              <button
                type="button"
                onClick={() => selectTag(null)}
                className="rounded border px-2 py-1 text-slate-600 hover:bg-slate-100"
              >
                清除
              </button>
            </div>
          )}
        </div>

        {papersQuery.isLoading && (
          <p className="text-sm text-slate-500">加载中...</p>
        )}
        {!papersQuery.isLoading && papers.length === 0 && (
          <p className="text-sm text-slate-500">
            {selectedTag ? `没有标签为「${selectedTag}」的论文。` : emptyText}
          </p>
        )}
        {papers.map((paper) => (
          <PaperCard key={paper.id} paper={paper} />
        ))}
      </section>
    </div>
  );
}
