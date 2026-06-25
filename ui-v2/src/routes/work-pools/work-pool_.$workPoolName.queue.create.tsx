import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { categorizeError } from "@/api/error-utils";
import { buildGetWorkPoolQuery } from "@/api/work-pools/work-pools";
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";
import {
	WorkPoolQueueCreatePageHeader,
	WorkPoolQueueForm,
} from "@/components/work-pools/work-pool-queue-form";

export const Route = createFileRoute(
	"/work-pools/work-pool_/$workPoolName/queue/create",
)({
	component: function RouteComponent() {
		const { workPoolName } = Route.useParams();
		const router = useRouter();

		const handleSubmit = () => {
			void router.navigate({
				to: "/work-pools/work-pool/$workPoolName",
				params: { workPoolName },
				search: { tab: "Work Queues" },
			});
		};

		const handleCancel = () => {
			router.history.back();
		};

		return (
			<div className="container max-w-4xl py-6">
				<WorkPoolQueueCreatePageHeader workPoolName={workPoolName} />
				<div className="mt-6">
					<WorkPoolQueueForm
						workPoolName={workPoolName}
						onSubmit={handleSubmit}
						onCancel={handleCancel}
					/>
				</div>
			</div>
		);
	},
	loader: async ({ params, context: { queryClient } }) => {
		// Validate the work pool exists
		await queryClient.ensureQueryData(
			buildGetWorkPoolQuery(params.workPoolName),
		);
	},
	errorComponent: function WorkPoolQueueCreateErrorComponent({
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
					<h1 className="text-2xl font-semibold">Create Work Queue</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
});
