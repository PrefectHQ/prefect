import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";

export const Route = createFileRoute("/blocks/catalog/$blockTypeSlug/create")({
  params: z.object({
    blockTypeSlug: z.string()
  }),
  loader: ({ params: { blockTypeSlug } }) => {
    // Add loader logic here to prepare for block creation
    return { blockTypeSlug };
  },
}); 