import type { Tag } from "../api/client";

export default function TagBadge({ tag }: { tag: Tag }) {
  return (
    <span
      title={tag.description ?? undefined}
      className="inline-block text-xs bg-blue-100 text-blue-800 rounded px-1.5 py-0.5 mr-1 mb-1"
    >
      {tag.name}
    </span>
  );
}
