import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";

export const Route = createFileRoute("/blocks/block/$blockDocumentId/edit")({
  params: z.object({
    blockDocumentId: z.string()
  }),
  loader: ({ params: { blockDocumentId } }) => {
    // Add loader logic here to fetch block document for editing
    return { blockDocumentId };
  },
}); 