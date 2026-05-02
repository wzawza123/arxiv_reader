import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { JobApi } from "../api/client";

const STATUS_COLOR: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800",
  running: "bg-blue-100 text-blue-800",
  done: "bg-emerald-100 text-emerald-800",
  failed: "bg-rose-100 text-rose-800",
};

export default function Jobs() {
  const qc = useQueryClient();
  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: JobApi.list,
    refetchInterval: 5_000,
  });
  const fetchNow = useMutation({
    mutationFn: JobApi.fetchNow,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["papers"] });
      qc.invalidateQueries({ queryKey: ["counts"] });
    },
  });

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xl font-semibold">后台任务</h2>
        <button
          disabled={fetchNow.isPending}
          onClick={() => fetchNow.mutate()}
          className="bg-blue-600 text-white px-3 py-1.5 rounded disabled:opacity-50"
        >
          {fetchNow.isPending ? "拉取中..." : "Fetch Now"}
        </button>
      </div>
      {fetchNow.data && (
        <p className="text-sm text-emerald-700 mb-2">
          已拉取 {fetchNow.data.new_papers} 篇新论文，入队 {fetchNow.data.queued} 个后台任务。
        </p>
      )}
      <table className="w-full text-sm bg-white border rounded">
        <thead className="text-xs text-slate-500 text-left">
          <tr>
            <th className="px-2 py-1.5">ID</th>
            <th>Kind</th>
            <th>Paper</th>
            <th>Status</th>
            <th>Started</th>
            <th>Finished</th>
            <th>Error</th>
          </tr>
        </thead>
        <tbody>
          {jobs.data?.map((j) => (
            <tr key={j.id} className="border-t">
              <td className="px-2 py-1.5 font-mono text-xs">{j.id}</td>
              <td>{j.kind}</td>
              <td>{j.paper_id ?? "—"}</td>
              <td>
                <span
                  className={`text-xs rounded px-1.5 py-0.5 ${STATUS_COLOR[j.status] ?? "bg-slate-100"}`}
                >
                  {j.status}
                </span>
              </td>
              <td className="text-xs">{j.started_at ?? "—"}</td>
              <td className="text-xs">{j.finished_at ?? "—"}</td>
              <td className="text-xs text-rose-600 max-w-xs truncate" title={j.error ?? ""}>
                {j.error ?? ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
