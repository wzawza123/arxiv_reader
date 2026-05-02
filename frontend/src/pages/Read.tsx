import PaperListWithTagFilter from "../components/PaperListWithTagFilter";

export default function Read() {
  return (
    <PaperListWithTagFilter
      title="已读"
      status="read"
      emptyText="还没有已读论文。"
    />
  );
}
