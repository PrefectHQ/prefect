import { TaskRunConcurrencyLimitPage } from "@/components/concurrency/task-run-concurrency-limit-page";
import { buildDetailTaskRunConcurrencyLimitsQuery } from "@/hooks/task-run-concurrency-limits";
import { createFileRoute } from "@tanstack/react-router";
import { zodSearchValidator } from "@tanstack/router-zod-adapter";
import { z } from "zod";

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
	validateSearch: zodSearchValidator(searchParams),
	component: RouteComponent,
	wrapInSuspense: true,
	loader: ({ context, params }) =>
		context.queryClient.ensureQueryData(
			buildDetailTaskRunConcurrencyLimitsQuery(params.id),
		),
});

function RouteComponent() {
	const { id } = Route.useParams();
	return <TaskRunConcurrencyLimitPage id={id} />;
}
