import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";

export const Route = createFileRoute("/blocks/catalog/$blockTypeSlug")({
  params: z.object({
    blockTypeSlug: z.string()
  }),
  loader: ({ params: { blockTypeSlug } }) => {
    // Add loader logic here to fetch specific block type details
    return { blockTypeSlug };
  },
}); 