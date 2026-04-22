import { useSuspenseQuery } from "@tanstack/react-query";
import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { categorizeError } from "@/api/error-utils";
import { buildWorkPoolQueueDetailsQuery } from "@/api/work-pool-queues";
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";
import {
	WorkPoolQueueEditPageHeader,
	WorkPoolQueueForm,
} from "@/components/work-pools/work-pool-queue-form";

export const Route = createFileRoute(
	"/work-pools/work-pool_/$workPoolName/queue_/$workQueueName/edit",
)({
	component: function RouteComponent() {
		const { workPoolName, workQueueName } = Route.useParams();
		const router = useRouter();

		const { data: queue } = useSuspenseQuery(
			buildWorkPoolQueueDetailsQuery(workPoolName, workQueueName),
		);

		const handleSubmit = (values: { name: string }) => {
			void router.navigate({
				to: "/work-pools/work-pool/$workPoolName/queue/$workQueueName",
				params: { workPoolName, workQueueName: values.name },
			});
		};

		const handleCancel = () => {
			router.history.back();
		};

		return (
			<div className="container max-w-4xl py-6">
				<WorkPoolQueueEditPageHeader
					workPoolName={workPoolName}
					workQueueName={workQueueName}
				/>
				<div className="mt-6">
					<WorkPoolQueueForm
						workPoolName={workPoolName}
						queueToEdit={queue}
						onSubmit={handleSubmit}
						onCancel={handleCancel}
					/>
				</div>
			</div>
		);
	},
	loader: async ({ params, context: { queryClient } }) => {
		await queryClient.ensureQueryData(
			buildWorkPoolQueueDetailsQuery(params.workPoolName, params.workQueueName),
		);
	},
	errorComponent: function WorkPoolQueueEditErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(error, "Failed to load work queue");
		if (
			serverError.type !== "server-error" &&
			serverError.type !== "client-error"
		) {
			throw error;
		}
		return (
			<div className="flex flex-col gap-4">
				<div>
					<h1 className="text-2xl font-semibold">Edit Work Queue</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
});
