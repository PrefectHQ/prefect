import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { categorizeError } from "@/api/error-utils";
import { buildConcurrenyLimitDetailsActiveRunsQuery } from "@/api/task-run-concurrency-limits";
import { TaskRunConcurrencyLimitPage } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limit-page";
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";

/**
 * Schema for validating URL search parameters for the Task Run Concurrency Limit Details page.
 * @property {'active-task-runs'} tab used designate which tab view to display
 */
const searchParams = z.object({
	tab: z.enum(["active-task-runs"]).default("active-task-runs"),
});

export type TabOptions = z.infer<typeof searchParams>["tab"];

export const Route = createFileRoute(
	"/concurrency-limits/concurrency-limit/$id",
)({
	validateSearch: zodValidator(searchParams),
	component: function RouteComponent() {
		const { id } = Route.useParams();
		return <TaskRunConcurrencyLimitPage id={id} />;
	},
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
	loader: ({ context, params }) =>
		context.queryClient.ensureQueryData(
			buildConcurrenyLimitDetailsActiveRunsQuery(params.id),
		),
	errorComponent: function ConcurrencyLimitDetailErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(
			error,
			"Failed to load concurrency limit",
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
					<h1 className="text-2xl font-semibold">Concurrency Limit</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
});
