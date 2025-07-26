import { createFileRoute } from "@tanstack/react-router";
import { buildListWorkPoolTypesQuery } from "@/api/collections/collections";
import { WorkPoolCreateWizard } from "@/components/work-pools/create";

export const Route = createFileRoute("/work-pools/create")({
	component: WorkPoolCreateWizard,
	loader: ({ context: { queryClient } }) => {
		// Prefetch worker types for infrastructure selection
		void queryClient.prefetchQuery(buildListWorkPoolTypesQuery());
	},
	wrapInSuspense: true,
});
