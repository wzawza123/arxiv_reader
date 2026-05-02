import { useQuery } from "@tanstack/react-query";
import { PaperApi } from "../api/client";
import PaperCard from "../components/PaperCard";

export default function Read() {
  const { data, isLoading } = useQuery({
    queryKey: ["papers", "read"],
    queryFn: () => PaperApi.list({ status: "read" }),
  });
  return (
    <section>
      <h2 className="text-xl font-semibold mb-3">已读</h2>
      {isLoading && <p className="text-sm text-slate-500">加载中...</p>}
      {data?.map((p) => <PaperCard key={p.id} paper={p} />)}
    </section>
  );
}
