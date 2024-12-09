import { Link } from "@tanstack/react-router";
import type { components } from "@/api/prefect";

type BlockDocument = components["schemas"]["BlockDocument"];




export function BlockNameCell({ row }: { row: { original: BlockDocument } }) {
  return (
    <Link
      to="/blocks/block/$blockDocumentId"
      params={{ blockDocumentId: row.original.id }}
      className="hover:underline"
    >
      {row.original.name}
    </Link>
  );
}

export function BlockTypeCell({ row }: { row: { original: BlockDocument } }) {
  return (
    <Link
      to="/blocks/catalog/$blockTypeSlug"
      params={{ blockTypeSlug: row.original.block_type?.slug }}
      className="hover:underline"
    >
      {row.original.block_type?.name}
    </Link>
  );
}