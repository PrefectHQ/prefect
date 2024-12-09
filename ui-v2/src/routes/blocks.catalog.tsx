import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/blocks/catalog")({
  loader: () => {
    // Add loader logic here to fetch block catalog data
    return {};
  },
}); 