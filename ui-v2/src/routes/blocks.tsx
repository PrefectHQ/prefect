import { buildListFilterBlockDocumentsQuery } from "@/api/block-documents";
import { buildListFilterBlockTypesQuery } from "@/api/block-types";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/blocks")({
	component: RouteComponent,
	loader: async ({ context: { queryClient } }) => {
		// ----- Critical data
		return Promise.all([
			queryClient.ensureQueryData(buildListFilterBlockTypesQuery()),
			queryClient.ensureQueryData(buildListFilterBlockDocumentsQuery()),
		]);
	},
	wrapInSuspense: true,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
