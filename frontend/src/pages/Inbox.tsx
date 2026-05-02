import PaperListWithTagFilter from "../components/PaperListWithTagFilter";

export default function Inbox() {
  return (
    <PaperListWithTagFilter
      title="收件箱（未分类）"
      status="new"
      emptyText="暂无新论文，去 设置 添加订阅或在 任务 页点击 “Fetch Now”。"
      refetchInterval={15_000}
    />
  );
}
