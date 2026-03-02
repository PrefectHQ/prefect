import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { buildListWorkPoolTypesQuery } from "@/api/collections/collections";
import { categorizeError } from "@/api/error-utils";
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";
import { WorkPoolCreateWizard } from "@/components/work-pools/create";

export const Route = createFileRoute("/work-pools/create")({
	component: WorkPoolCreateWizard,
	loader: ({ context: { queryClient } }) => {
		// Prefetch worker types for infrastructure selection
		void queryClient.prefetchQuery(buildListWorkPoolTypesQuery());
	},
	errorComponent: function WorkPoolCreateErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(
			error,
			"Failed to load work pool creation form",
		);
		if (
			serverError.type !== "server-error" &&
			serverError.type !== "client-error"
		) {
			throw error;
		}
		return (
			<div className="flex flex-col gap-4">
				<div>
					<h1 className="text-2xl font-semibold">Create Work Pool</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
});
