import { useQuery } from "@tanstack/react-query";
import { PaperApi } from "../api/client";
import PaperCard from "../components/PaperCard";

export default function Inbox() {
  const { data, isLoading } = useQuery({
    queryKey: ["papers", "new"],
    queryFn: () => PaperApi.list({ status: "new" }),
    refetchInterval: 15_000,
  });
  return (
    <section>
      <h2 className="text-xl font-semibold mb-3">收件箱（未分类）</h2>
      {isLoading && <p className="text-sm text-slate-500">加载中...</p>}
      {data?.length === 0 && (
        <p className="text-sm text-slate-500">
          暂无新论文，去 设置 添加订阅或在 任务 页点击 “Fetch Now”。
        </p>
      )}
      {data?.map((p) => <PaperCard key={p.id} paper={p} />)}
    </section>
  );
}
