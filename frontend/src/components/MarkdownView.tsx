import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function MarkdownView({ md }: { md: string | null | undefined }) {
  if (!md) return <span className="text-slate-400 text-sm">（暂无内容）</span>;
  return (
    <div className="markdown text-sm">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{md}</ReactMarkdown>
    </div>
  );
}
