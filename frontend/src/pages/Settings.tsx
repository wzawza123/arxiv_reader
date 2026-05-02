import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PaperApi, SettingsApi, SubsApi, TagApi, type Tag } from "../api/client";

const COMMON_CATEGORIES = [
  "cs.AI",
  "cs.CV",
  "cs.LG",
  "cs.CL",
  "cs.RO",
  "cs.IR",
  "cs.GR",
  "cs.MM",
  "cs.SE",
  "cs.DB",
];

function getErrorMessage(error: unknown) {
  if (typeof error === "object" && error !== null && "response" in error) {
    const data = (error as { response?: { data?: { detail?: unknown } } }).response?.data;
    if (typeof data?.detail === "string") return data.detail;
  }
  if (error instanceof Error) return error.message;
  return "操作失败";
}

export default function Settings() {
  const qc = useQueryClient();
  const subs = useQuery({ queryKey: ["subs"], queryFn: SubsApi.list });
  const tags = useQuery({ queryKey: ["tags"], queryFn: TagApi.list });
  const fetchSettings = useQuery({
    queryKey: ["fetch-settings"],
    queryFn: SettingsApi.getFetch,
  });
  const paperCounts = useQuery({
    queryKey: ["counts"],
    queryFn: PaperApi.counts,
  });

  const [kind, setKind] = useState<"category" | "keyword">("category");
  const [value, setValue] = useState("");
  const [fetchLookbackDays, setFetchLookbackDays] = useState<string | null>(null);
  const [tagName, setTagName] = useState("");
  const [tagDescription, setTagDescription] = useState("");
  const [editingTag, setEditingTag] = useState<{
    id: number;
    name: string;
    description: string;
  } | null>(null);
  const [tagError, setTagError] = useState<string | null>(null);

  const invalidateTags = () => {
    qc.invalidateQueries({ queryKey: ["tags"] });
    qc.invalidateQueries({ queryKey: ["papers"] });
    qc.invalidateQueries({ queryKey: ["paper"] });
  };

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

  const updateFetchSettings = useMutation({
    mutationFn: () =>
      SettingsApi.updateFetch({
        fetch_lookback_days: Number(fetchLookbackDays),
      }),
    onSuccess: (data) => {
      setFetchLookbackDays(String(data.fetch_lookback_days));
      qc.invalidateQueries({ queryKey: ["fetch-settings"] });
    },
  });

  const removeTag = useMutation({
    mutationFn: (id: number) => TagApi.remove(id),
    onSuccess: (_data, id) => {
      if (editingTag?.id === id) setEditingTag(null);
      setTagError(null);
      invalidateTags();
    },
    onError: (error) => setTagError(getErrorMessage(error)),
  });

  const createTag = useMutation({
    mutationFn: () =>
      TagApi.create({
        name: tagName,
        description: tagDescription,
      }),
    onSuccess: () => {
      setTagName("");
      setTagDescription("");
      setTagError(null);
      invalidateTags();
    },
    onError: (error) => setTagError(getErrorMessage(error)),
  });

  const updateTag = useMutation({
    mutationFn: (tag: { id: number; name: string; description: string }) =>
      TagApi.update(tag.id, {
        name: tag.name,
        description: tag.description,
      }),
    onSuccess: () => {
      setEditingTag(null);
      setTagError(null);
      invalidateTags();
    },
    onError: (error) => setTagError(getErrorMessage(error)),
  });

  const clearAllPapers = useMutation({
    mutationFn: PaperApi.clearAll,
    onSuccess: () => {
      qc.setQueryData(["counts"], {
        new: 0,
        to_read: 0,
        read: 0,
        not_interested: 0,
      });
      qc.invalidateQueries({ queryKey: ["papers"] });
      qc.invalidateQueries({ queryKey: ["paper"] });
      qc.invalidateQueries({ queryKey: ["counts"] });
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["tags"] });
    },
    onError: () => {
      window.alert("清空失败，请检查后端服务或稍后重试。");
    },
  });

  const startTagEdit = (tag: Tag) => {
    setTagError(null);
    setEditingTag({
      id: tag.id,
      name: tag.name,
      description: tag.description ?? "",
    });
  };

  const currentFetchLookback =
    fetchSettings.data?.fetch_lookback_days ??
    fetchSettings.data?.default_fetch_lookback_days;
  const fetchLookbackValue =
    fetchLookbackDays ?? (currentFetchLookback !== undefined ? String(currentFetchLookback) : "");
  const parsedFetchLookback = Number(fetchLookbackValue);
  const canSaveFetchLookback =
    currentFetchLookback !== undefined &&
    Number.isInteger(parsedFetchLookback) &&
    parsedFetchLookback >= 1 &&
    parsedFetchLookback <= 365 &&
    parsedFetchLookback !== currentFetchLookback;
  const totalPapers = Object.values(paperCounts.data ?? {}).reduce(
    (sum, count) => sum + count,
    0,
  );

  const handleClearAllPapers = () => {
    if (
      window.confirm(
        "确定清空所有论文列表？这会删除所有 paper、关联任务和 figure 记录。",
      )
    ) {
      clearAllPapers.mutate();
    }
  };

  return (
    <section className="space-y-6">
      <div className="bg-white border rounded p-4">
        <h2 className="font-semibold mb-3">拉取设置</h2>
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <label className="block">
            <span className="block text-xs text-slate-500 mb-1">
              只保留近 N 天发表的论文
            </span>
            <input
              type="number"
              min={1}
              max={365}
              value={fetchLookbackValue}
              onChange={(e) => {
                updateFetchSettings.reset();
                setFetchLookbackDays(e.target.value);
              }}
              className="border rounded px-2 py-1 w-32"
            />
          </label>
          <button
            disabled={!canSaveFetchLookback || updateFetchSettings.isPending}
            onClick={() => updateFetchSettings.mutate()}
            className="bg-slate-800 text-white px-3 py-1 rounded disabled:opacity-50"
          >
            保存
          </button>
          {fetchSettings.data && (
            <span className="text-xs text-slate-500">
              默认值：{fetchSettings.data.default_fetch_lookback_days} 天
            </span>
          )}
        </div>
        {updateFetchSettings.isSuccess && (
          <p className="text-xs text-emerald-700 mt-2">已保存，下次 Fetch 生效。</p>
        )}
        {updateFetchSettings.isError && (
          <p className="text-xs text-rose-600 mt-2">
            {getErrorMessage(updateFetchSettings.error)}
          </p>
        )}
      </div>

      <div className="bg-white border rounded p-4">
        <h2 className="font-semibold mb-3">数据维护</h2>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <button
            type="button"
            onClick={handleClearAllPapers}
            disabled={totalPapers === 0 || clearAllPapers.isPending}
            className="px-3 py-1.5 rounded border border-red-200 text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {clearAllPapers.isPending ? "清空中..." : "清空论文"}
          </button>
          <span className="text-xs text-slate-500">当前共有 {totalPapers} 篇论文</span>
        </div>
        {clearAllPapers.isSuccess && (
          <p className="text-xs text-emerald-700 mt-2">
            已清空 {clearAllPapers.data.deleted} 篇论文。
          </p>
        )}
      </div>

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
          Tag 可由 LLM 在拉取时自动维护，也可以在这里手动新增、重命名和补充描述。
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (tagName.trim()) createTag.mutate();
          }}
          className="grid grid-cols-1 md:grid-cols-[minmax(180px,240px)_1fr_auto] gap-2 mb-3 text-sm"
        >
          <input
            value={tagName}
            onChange={(e) => setTagName(e.target.value)}
            placeholder="tag name"
            className="border rounded px-2 py-1"
          />
          <input
            value={tagDescription}
            onChange={(e) => setTagDescription(e.target.value)}
            placeholder="description"
            className="border rounded px-2 py-1"
          />
          <button
            type="submit"
            disabled={!tagName.trim() || createTag.isPending}
            className="bg-slate-800 text-white px-3 py-1 rounded disabled:opacity-50"
          >
            添加 Tag
          </button>
        </form>
        {tagError && <p className="text-xs text-rose-600 mb-2">{tagError}</p>}
        <table className="text-sm w-full">
          <thead className="text-left text-xs text-slate-500">
            <tr>
              <th className="py-1">Name</th>
              <th>Description</th>
              <th>Papers</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {tags.data?.map((t) => {
              const isEditing = editingTag?.id === t.id;
              return (
                <tr key={t.id} className="border-t align-top">
                  <td className="py-1.5 pr-2">
                    {isEditing ? (
                      <input
                        value={editingTag.name}
                        onChange={(e) =>
                          setEditingTag({ ...editingTag, name: e.target.value })
                        }
                        className="border rounded px-2 py-1 w-full"
                      />
                    ) : (
                      <span className="font-mono text-xs">{t.name}</span>
                    )}
                  </td>
                  <td className="py-1.5 pr-2 text-xs text-slate-600">
                    {isEditing ? (
                      <input
                        value={editingTag.description}
                        onChange={(e) =>
                          setEditingTag({ ...editingTag, description: e.target.value })
                        }
                        className="border rounded px-2 py-1 w-full text-sm text-slate-800"
                      />
                    ) : (
                      t.description || <span className="text-slate-400">无描述</span>
                    )}
                  </td>
                  <td className="py-1.5 text-xs text-slate-500">
                    {t.paper_count ?? 0}
                  </td>
                  <td className="py-1.5 text-right whitespace-nowrap">
                    {isEditing ? (
                      <>
                        <button
                          disabled={!editingTag.name.trim() || updateTag.isPending}
                          onClick={() => updateTag.mutate(editingTag)}
                          className="text-blue-600 text-xs hover:underline disabled:opacity-50"
                        >
                          保存
                        </button>
                        <button
                          onClick={() => setEditingTag(null)}
                          className="text-slate-500 text-xs hover:underline ml-3"
                        >
                          取消
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          onClick={() => startTagEdit(t)}
                          className="text-blue-600 text-xs hover:underline"
                        >
                          编辑
                        </button>
                        <button
                          onClick={() => {
                            if (confirm(`删除 tag "${t.name}"?`)) removeTag.mutate(t.id);
                          }}
                          className="text-rose-600 text-xs hover:underline ml-3"
                        >
                          删除
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
            {tags.data?.length === 0 && (
              <tr>
                <td colSpan={4} className="py-3 text-slate-400 text-sm text-center">
                  尚无 tag
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
