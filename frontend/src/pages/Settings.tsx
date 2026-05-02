import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { SubsApi, TagApi } from "../api/client";

const COMMON_CATEGORIES = [
  "cs.AI",
  "cs.CV",
  "cs.LG",
  "cs.CL",
  "cs.RO",
  "cs.IR",
  "cs.GR",
  "cs.MM",
  "stat.ML",
  "eess.IV",
];

export default function Settings() {
  const qc = useQueryClient();
  const subs = useQuery({ queryKey: ["subs"], queryFn: SubsApi.list });
  const tags = useQuery({ queryKey: ["tags"], queryFn: TagApi.list });

  const [kind, setKind] = useState<"category" | "keyword">("category");
  const [value, setValue] = useState("");

  const create = useMutation({
    mutationFn: () => SubsApi.create({ kind, value: value.trim(), enabled: true }),
    onSuccess: () => {
      setValue("");
      qc.invalidateQueries({ queryKey: ["subs"] });
    },
  });

  const toggle = useMutation({
    mutationFn: (s: { id: number; kind: string; value: string; enabled: boolean }) =>
      SubsApi.update(s.id, { kind: s.kind, value: s.value, enabled: !s.enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subs"] }),
  });

  const remove = useMutation({
    mutationFn: (id: number) => SubsApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subs"] }),
  });

  const removeTag = useMutation({
    mutationFn: (id: number) => TagApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tags"] }),
  });

  return (
    <section className="space-y-6">
      <div className="bg-white border rounded p-4">
        <h2 className="font-semibold mb-3">订阅 (Subscriptions)</h2>
        <div className="flex flex-wrap items-center gap-2 mb-3 text-sm">
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as "category" | "keyword")}
            className="border rounded px-2 py-1"
          >
            <option value="category">category (e.g. cs.CV)</option>
            <option value="keyword">keyword</option>
          </select>
          {kind === "category" ? (
            <input
              list="cats"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="cs.CV"
              className="border rounded px-2 py-1"
            />
          ) : (
            <input
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="diffusion model"
              className="border rounded px-2 py-1 w-72"
            />
          )}
          <datalist id="cats">
            {COMMON_CATEGORIES.map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
          <button
            disabled={!value.trim() || create.isPending}
            onClick={() => create.mutate()}
            className="bg-slate-800 text-white px-3 py-1 rounded disabled:opacity-50"
          >
            添加
          </button>
        </div>
        <table className="text-sm w-full">
          <thead className="text-left text-xs text-slate-500">
            <tr>
              <th className="py-1">Kind</th>
              <th>Value</th>
              <th>Enabled</th>
              <th>Last fetched</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {subs.data?.map((s) => (
              <tr key={s.id} className="border-t">
                <td className="py-1.5">{s.kind}</td>
                <td className="font-mono">{s.value}</td>
                <td>
                  <input
                    type="checkbox"
                    checked={s.enabled}
                    onChange={() => toggle.mutate(s)}
                  />
                </td>
                <td className="text-xs text-slate-500">
                  {s.last_fetched_at ? new Date(s.last_fetched_at).toLocaleString() : "—"}
                </td>
                <td>
                  <button
                    onClick={() => remove.mutate(s.id)}
                    className="text-rose-600 text-xs hover:underline"
                  >
                    删除
                  </button>
                </td>
              </tr>
            ))}
            {subs.data?.length === 0 && (
              <tr>
                <td colSpan={5} className="py-3 text-slate-400 text-sm text-center">
                  尚无订阅
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="bg-white border rounded p-4">
        <h2 className="font-semibold mb-3">Tag 库</h2>
        <p className="text-xs text-slate-500 mb-2">
          Tag 由 LLM 在拉取时自动维护；这里只能查看 / 删除。
        </p>
        <div className="flex flex-wrap gap-1.5">
          {tags.data?.map((t) => (
            <span
              key={t.id}
              className="inline-flex items-center gap-1 text-xs bg-slate-100 border rounded px-2 py-1"
              title={t.description ?? ""}
            >
              {t.name}
              <span className="text-slate-400">({t.paper_count ?? 0})</span>
              <button
                onClick={() => {
                  if (confirm(`删除 tag "${t.name}"?`)) removeTag.mutate(t.id);
                }}
                className="text-rose-500 ml-0.5"
              >
                ×
              </button>
            </span>
          ))}
          {tags.data?.length === 0 && (
            <span className="text-sm text-slate-400">尚无 tag</span>
          )}
        </div>
      </div>
    </section>
  );
}
