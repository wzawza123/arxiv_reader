import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { PaperListItem } from "../api/client";
import { PaperApi } from "../api/client";
import TagBadge from "./TagBadge";

function fmtDate(s: string) {
  return new Date(s).toLocaleDateString();
}

const STATUS_BUTTONS: { label: string; status: string; cls: string }[] = [
  { label: "待阅读", status: "to_read", cls: "bg-emerald-600 hover:bg-emerald-700" },
  { label: "已读", status: "read", cls: "bg-slate-600 hover:bg-slate-700" },
  { label: "不感兴趣", status: "not_interested", cls: "bg-rose-600 hover:bg-rose-700" },
];

type PaperListContext = {
  status: PaperListItem["status"];
  tag?: string;
};

function detailLinkTo(paperId: number, context?: PaperListContext) {
  const params = new URLSearchParams();
  if (context?.status) params.set("status", context.status);
  if (context?.tag) params.set("tag", context.tag);

  const search = params.toString();
  return {
    pathname: `/papers/${paperId}`,
    search: search ? `?${search}` : "",
  };
}

export default function PaperCard({
  paper,
  listContext,
}: {
  paper: PaperListItem;
  listContext?: PaperListContext;
}) {
  const [showZh, setShowZh] = useState(true);
  const qc = useQueryClient();
  const mutate = useMutation({
    mutationFn: (status: string) => PaperApi.patch(paper.id, { status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["papers"] });
      qc.invalidateQueries({ queryKey: ["counts"] });
    },
  });

  const abstract = showZh && paper.abstract_zh ? paper.abstract_zh : paper.abstract;
  const hasZh = !!paper.abstract_zh;

  return (
    <div className="bg-white border rounded-lg p-4 mb-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <h3 className="font-semibold text-base">
            <Link
              to={detailLinkTo(paper.id, listContext)}
              className="hover:text-blue-700"
            >
              {paper.title}
            </Link>
          </h3>
          <div className="text-xs text-slate-500 mt-1">
            {paper.authors.slice(0, 5).join(", ")}
            {paper.authors.length > 5 && " et al."}
            <span className="mx-2">·</span>
            {fmtDate(paper.published_at)}
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
        </div>
      </div>
      <div className="mt-2">
        {paper.tags.map((t) => (
          <TagBadge key={t.id} tag={t} />
        ))}
      </div>
      <div className="mt-2 text-sm text-slate-700 leading-relaxed">
        {abstract || <span className="text-slate-400">（摘要为空）</span>}
      </div>
      <div className="mt-3 flex items-center gap-2 text-xs">
        {hasZh && (
          <button
            onClick={() => setShowZh((v) => !v)}
            className="px-2 py-1 rounded border text-slate-600"
          >
            {showZh ? "查看原文" : "查看中文"}
          </button>
        )}
        <div className="flex-1" />
        {STATUS_BUTTONS.map(
          (b) =>
            paper.status !== b.status && (
              <button
                key={b.status}
                disabled={mutate.isPending}
                onClick={() => mutate.mutate(b.status)}
                className={`px-2 py-1 rounded text-white ${b.cls} disabled:opacity-50`}
              >
                {b.label}
              </button>
            ),
        )}
      </div>
    </div>
  );
}
