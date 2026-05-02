import {
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type WheelEvent as ReactWheelEvent,
} from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PaperApi, type Figure } from "../api/client";
import MarkdownView from "../components/MarkdownView";
import TagBadge from "../components/TagBadge";

const REPROCESS_STAGES: { label: string; stage: "translate" | "tag" | "summary" | "figures" }[] = [
  { label: "翻译", stage: "translate" },
  { label: "Tag", stage: "tag" },
  { label: "总结", stage: "summary" },
  { label: "Figures", stage: "figures" },
];

const MIN_ZOOM = 0.3;
const MAX_ZOOM = 6;
const ZOOM_STEP = 1.2;

function clampZoom(value: number) {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Number(value.toFixed(3))));
}

export default function PaperDetail() {
  const { id } = useParams();
  const pid = Number(id);
  const qc = useQueryClient();
  const [previewFigure, setPreviewFigure] = useState<Figure | null>(null);
  const [previewZoom, setPreviewZoom] = useState(1);
  const [previewOffset, setPreviewOffset] = useState({ x: 0, y: 0 });
  const [isDraggingPreview, setIsDraggingPreview] = useState(false);
  const dragStartRef = useRef<{
    pointerX: number;
    pointerY: number;
    offsetX: number;
    offsetY: number;
  } | null>(null);
  const { data: paper, isLoading } = useQuery({
    queryKey: ["paper", pid],
    queryFn: () => PaperApi.get(pid),
    refetchInterval: 8_000,
  });
  const figures = paper?.figures ?? [];
  const previewFigureIndex = previewFigure
    ? figures.findIndex((figure) => figure.id === previewFigure.id)
    : -1;
  const hasPreviousFigure = previewFigureIndex > 0;
  const hasNextFigure = previewFigureIndex >= 0 && previewFigureIndex < figures.length - 1;

  const reprocess = useMutation({
    mutationFn: (stage: "translate" | "tag" | "summary" | "figures") =>
      PaperApi.reprocess(pid, stage),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["paper", pid] });
      qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const closeFigurePreview = () => {
    setPreviewFigure(null);
    setIsDraggingPreview(false);
    dragStartRef.current = null;
  };

  const resetFigurePreview = () => {
    setPreviewZoom(1);
    setPreviewOffset({ x: 0, y: 0 });
  };

  const openFigurePreview = (figure: Figure) => {
    setPreviewFigure(figure);
    resetFigurePreview();
  };

  const showFigureAtIndex = (index: number) => {
    const figure = figures[index];
    if (!figure) return;
    setPreviewFigure(figure);
    resetFigurePreview();
  };

  const showPreviousFigure = () => {
    showFigureAtIndex(previewFigureIndex - 1);
  };

  const showNextFigure = () => {
    showFigureAtIndex(previewFigureIndex + 1);
  };

  const zoomFigurePreview = (direction: "in" | "out") => {
    setPreviewZoom((current) =>
      clampZoom(direction === "in" ? current * ZOOM_STEP : current / ZOOM_STEP),
    );
  };

  const handlePreviewWheel = (event: ReactWheelEvent<HTMLDivElement>) => {
    event.preventDefault();
    setPreviewZoom((current) =>
      clampZoom(event.deltaY < 0 ? current * ZOOM_STEP : current / ZOOM_STEP),
    );
  };

  const handlePreviewPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!event.isPrimary) return;
    if (event.target === event.currentTarget) {
      closeFigurePreview();
      return;
    }
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    setIsDraggingPreview(true);
    dragStartRef.current = {
      pointerX: event.clientX,
      pointerY: event.clientY,
      offsetX: previewOffset.x,
      offsetY: previewOffset.y,
    };
  };

  const handlePreviewPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!isDraggingPreview || !dragStartRef.current) return;
    const start = dragStartRef.current;
    setPreviewOffset({
      x: start.offsetX + event.clientX - start.pointerX,
      y: start.offsetY + event.clientY - start.pointerY,
    });
  };

  const handlePreviewPointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    setIsDraggingPreview(false);
    dragStartRef.current = null;
  };

  useEffect(() => {
    if (!previewFigure) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeFigurePreview();
      } else if (event.key === "+" || event.key === "=") {
        zoomFigurePreview("in");
      } else if (event.key === "-") {
        zoomFigurePreview("out");
      } else if (event.key === "0") {
        resetFigurePreview();
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        showPreviousFigure();
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        showNextFigure();
      }
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [previewFigure, previewFigureIndex, figures]);

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
                  : "可按设置自动提取，也可在这里手动重跑 Figures。"}
              </p>
            )}
            <div className="grid grid-cols-2 gap-2">
              {paper.figures.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => openFigurePreview(f)}
                  className="block text-left"
                >
                  <img
                    src={`/figures/${f.path}`}
                    alt={f.caption ?? `figure ${f.idx}`}
                    className="w-full h-auto border rounded transition hover:border-blue-400"
                    loading="lazy"
                  />
                  {f.caption && (
                    <div className="text-[10px] text-slate-500 mt-1 line-clamp-2">
                      {f.caption}
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>
        </aside>
      </div>

      {previewFigure && (
        <div
          className="fixed inset-0 z-50 bg-slate-950/90 text-white"
          role="dialog"
          aria-modal="true"
          aria-label="Figure 预览"
        >
          <div className="absolute inset-x-0 top-0 z-10 flex flex-wrap items-center justify-between gap-3 border-b border-white/10 bg-slate-950/80 px-4 py-3 backdrop-blur">
            <div className="min-w-0">
              <div className="text-sm font-medium">
                Figure {previewFigure.idx}
                {previewFigureIndex >= 0 && (
                  <span className="ml-2 text-xs font-normal text-slate-400">
                    {previewFigureIndex + 1} / {figures.length}
                  </span>
                )}
              </div>
              {previewFigure.caption && (
                <div className="mt-0.5 max-w-3xl truncate text-xs text-slate-300">
                  {previewFigure.caption}
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => zoomFigurePreview("out")}
                className="rounded border border-white/20 px-3 py-1.5 text-sm hover:bg-white/10"
              >
                缩小
              </button>
              <div className="w-14 text-center text-xs tabular-nums text-slate-300">
                {Math.round(previewZoom * 100)}%
              </div>
              <button
                type="button"
                onClick={() => zoomFigurePreview("in")}
                className="rounded border border-white/20 px-3 py-1.5 text-sm hover:bg-white/10"
              >
                放大
              </button>
              <button
                type="button"
                onClick={resetFigurePreview}
                className="rounded border border-white/20 px-3 py-1.5 text-sm hover:bg-white/10"
              >
                重置
              </button>
              <button
                type="button"
                onClick={closeFigurePreview}
                className="rounded border border-white/20 px-3 py-1.5 text-sm hover:bg-white/10"
              >
                关闭
              </button>
            </div>
          </div>

          {figures.length > 1 && (
            <>
              <button
                type="button"
                onClick={showPreviousFigure}
                disabled={!hasPreviousFigure}
                aria-label="上一张 figure"
                className="absolute left-4 top-1/2 z-20 flex h-12 w-12 -translate-y-1/2 items-center justify-center rounded-full border border-white/20 bg-slate-950/70 text-3xl leading-none text-white shadow-lg transition hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-slate-950/70"
              >
                ‹
              </button>
              <button
                type="button"
                onClick={showNextFigure}
                disabled={!hasNextFigure}
                aria-label="下一张 figure"
                className="absolute right-4 top-1/2 z-20 flex h-12 w-12 -translate-y-1/2 items-center justify-center rounded-full border border-white/20 bg-slate-950/70 text-3xl leading-none text-white shadow-lg transition hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-slate-950/70"
              >
                ›
              </button>
            </>
          )}

          <div
            className={`absolute inset-0 flex touch-none select-none items-center justify-center overflow-hidden px-4 pt-20 pb-6 ${
              isDraggingPreview ? "cursor-grabbing" : "cursor-grab"
            }`}
            onWheel={handlePreviewWheel}
            onPointerDown={handlePreviewPointerDown}
            onPointerMove={handlePreviewPointerMove}
            onPointerUp={handlePreviewPointerUp}
            onPointerCancel={handlePreviewPointerUp}
          >
            <img
              src={`/figures/${previewFigure.path}`}
              alt={previewFigure.caption ?? `figure ${previewFigure.idx}`}
              className="max-h-[82vh] max-w-[92vw] rounded bg-white shadow-2xl"
              draggable={false}
              style={{
                transform: `translate(${previewOffset.x}px, ${previewOffset.y}px) scale(${previewZoom})`,
                transformOrigin: "center",
              }}
            />
          </div>
        </div>
      )}
    </section>
  );
}
