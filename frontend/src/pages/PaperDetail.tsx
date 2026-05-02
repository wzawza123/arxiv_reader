import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PaperApi } from "../api/client";
import MarkdownView from "../components/MarkdownView";
import TagBadge from "../components/TagBadge";

const REPROCESS_STAGES: { label: string; stage: "translate" | "tag" | "summary" | "figures" }[] = [
  { label: "翻译", stage: "translate" },
  { label: "Tag", stage: "tag" },
  { label: "总结", stage: "summary" },
  { label: "Figures", stage: "figures" },
];

export default function PaperDetail() {
  const { id } = useParams();
  const pid = Number(id);
  const qc = useQueryClient();
  const { data: paper, isLoading } = useQuery({
    queryKey: ["paper", pid],
    queryFn: () => PaperApi.get(pid),
    refetchInterval: 8_000,
  });

  const reprocess = useMutation({
    mutationFn: (stage: "translate" | "tag" | "summary" | "figures") =>
      PaperApi.reprocess(pid, stage),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["paper", pid] });
      qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  if (isLoading || !paper) return <p className="text-sm text-slate-500">加载中...</p>;

  return (
    <section>
      <h2 className="text-xl font-semibold">{paper.title}</h2>
      <div className="text-xs text-slate-500 mt-1">
        {paper.authors.join(", ")}
        <span className="mx-2">·</span>
        {paper.categories.join(", ")}
        <span className="mx-2">·</span>
        <a
          href={paper.abs_url}
          target="_blank"
          rel="noreferrer"
          className="text-blue-600 underline"
        >
          arXiv
        </a>
        <span className="mx-1">|</span>
        <a
          href={paper.pdf_url}
          target="_blank"
          rel="noreferrer"
          className="text-blue-600 underline"
        >
          PDF
        </a>
      </div>
      <div className="mt-2">
        {paper.tags.map((t) => (
          <TagBadge key={t.id} tag={t} />
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
        <div className="md:col-span-2 space-y-4">
          <div className="bg-white border rounded p-4">
            <h3 className="font-semibold text-sm text-slate-600 mb-2">摘要 (中文)</h3>
            <p className="text-sm leading-relaxed text-slate-800 whitespace-pre-wrap">
              {paper.abstract_zh || <span className="text-slate-400">（翻译中或不可用）</span>}
            </p>
            <details className="mt-3 text-xs">
              <summary className="cursor-pointer text-slate-500">原文摘要</summary>
              <p className="mt-2 text-slate-700 whitespace-pre-wrap">{paper.abstract}</p>
            </details>
          </div>
          <div className="bg-white border rounded p-4">
            <h3 className="font-semibold text-sm text-slate-600 mb-2">1. 这篇论文尝试解决什么问题</h3>
            <MarkdownView md={paper.summary_md} />
          </div>
          <div className="bg-white border rounded p-4">
            <h3 className="font-semibold text-sm text-slate-600 mb-2">2. 关键 Insight</h3>
            <MarkdownView md={paper.insights_md} />
          </div>
          <div className="bg-white border rounded p-4">
            <h3 className="font-semibold text-sm text-slate-600 mb-2">3. 后续工作头脑风暴</h3>
            <MarkdownView md={paper.followup_md} />
          </div>
        </div>
        <aside className="space-y-4">
          <div className="bg-white border rounded p-4">
            <h3 className="font-semibold text-sm text-slate-600 mb-2">操作</h3>
            <div className="flex flex-wrap gap-2">
              {REPROCESS_STAGES.map((s) => (
                <button
                  key={s.stage}
                  disabled={reprocess.isPending}
                  onClick={() => reprocess.mutate(s.stage)}
                  className="text-xs px-2 py-1 border rounded hover:bg-slate-50"
                >
                  重跑：{s.label}
                </button>
              ))}
            </div>
          </div>
          <div className="bg-white border rounded p-4">
            <h3 className="font-semibold text-sm text-slate-600 mb-2">
              Figures ({paper.figures.length})
            </h3>
            {paper.figures.length === 0 && (
              <p className="text-xs text-slate-400">
                {paper.status === "to_read"
                  ? "正在提取或暂未提取到 figure。"
                  : "标记为待阅读后会自动提取。"}
              </p>
            )}
            <div className="grid grid-cols-2 gap-2">
              {paper.figures.map((f) => (
                <a
                  key={f.id}
                  href={`/figures/${f.path}`}
                  target="_blank"
                  rel="noreferrer"
                  className="block"
                >
                  <img
                    src={`/figures/${f.path}`}
                    alt={f.caption ?? `figure ${f.idx}`}
                    className="w-full h-auto border rounded"
                    loading="lazy"
                  />
                  {f.caption && (
                    <div className="text-[10px] text-slate-500 mt-1 line-clamp-2">
                      {f.caption}
                    </div>
                  )}
                </a>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}
