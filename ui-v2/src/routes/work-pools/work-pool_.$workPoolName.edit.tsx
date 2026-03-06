import { useSuspenseQuery } from "@tanstack/react-query";
import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { categorizeError } from "@/api/error-utils";
import { buildGetWorkPoolQuery } from "@/api/work-pools/work-pools";
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";
import {
	WorkPoolEditForm,
	WorkPoolEditPageHeader,
} from "@/components/work-pools/edit";

export const Route = createFileRoute(
	"/work-pools/work-pool_/$workPoolName/edit",
)({
	component: function RouteComponent() {
		const { workPoolName } = Route.useParams();
		const { data: workPool } = useSuspenseQuery(
			buildGetWorkPoolQuery(workPoolName),
		);

		return (
			<div className="container max-w-4xl py-6">
				<WorkPoolEditPageHeader workPool={workPool} />
				<WorkPoolEditForm workPool={workPool} />
			</div>
		);
	},
	loader: async ({ context, params }) => {
		const { workPoolName } = params;
		return context.queryClient.ensureQueryData(
			buildGetWorkPoolQuery(workPoolName),
		);
	},
	errorComponent: function WorkPoolEditErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(error, "Failed to load work pool");
		if (
			serverError.type !== "server-error" &&
			serverError.type !== "client-error"
		) {
			throw error;
		}
		return (
			<div className="flex flex-col gap-4">
				<div>
					<h1 className="text-2xl font-semibold">Edit Work Pool</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
});
