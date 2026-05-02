import PaperListWithTagFilter from "../components/PaperListWithTagFilter";

export default function NotInterested() {
  return (
    <PaperListWithTagFilter
      title="不感兴趣"
      status="not_interested"
      emptyText="还没有不感兴趣的论文。"
    />
  );
}
