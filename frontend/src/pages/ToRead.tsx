import { useQuery } from "@tanstack/react-query";
import { PaperApi } from "../api/client";
import PaperCard from "../components/PaperCard";

export default function ToRead() {
  const { data, isLoading } = useQuery({
    queryKey: ["papers", "to_read"],
    queryFn: () => PaperApi.list({ status: "to_read" }),
    refetchInterval: 15_000,
  });
  return (
    <section>
      <h2 className="text-xl font-semibold mb-3">待阅读</h2>
      <p className="text-xs text-slate-500 mb-3">
        标记为「待阅读」后，后台会自动跑 LLM 总结 + Docling figure 提取。
      </p>
      {isLoading && <p className="text-sm text-slate-500">加载中...</p>}
      {data?.length === 0 && (
        <p className="text-sm text-slate-500">还没有标记任何论文为待阅读。</p>
      )}
      {data?.map((p) => <PaperCard key={p.id} paper={p} />)}
    </section>
  );
}
