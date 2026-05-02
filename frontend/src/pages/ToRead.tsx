import PaperListWithTagFilter from "../components/PaperListWithTagFilter";

export default function ToRead() {
  return (
    <PaperListWithTagFilter
      title="待阅读"
      status="to_read"
      description={
        <p className="mt-1 text-xs text-slate-500">
          标记为「待阅读」后，后台会自动跑 LLM 总结 + Docling figure 提取。
        </p>
      }
      emptyText="还没有标记任何论文为待阅读。"
      refetchInterval={15_000}
    />
  );
}
