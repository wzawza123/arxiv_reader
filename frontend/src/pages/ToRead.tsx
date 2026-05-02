import PaperListWithTagFilter from "../components/PaperListWithTagFilter";

export default function ToRead() {
  return (
    <PaperListWithTagFilter
      title="待阅读"
      status="to_read"
      description={
        <p className="mt-1 text-xs text-slate-500">
          LLM 总结 + Docling figure 提取可在设置页选择 Fetch 时或标记「待阅读」时触发。
        </p>
      }
      emptyText="还没有标记任何论文为待阅读。"
      refetchInterval={15_000}
    />
  );
}
