import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { buildConcurrenyLimitDetailsActiveRunsQuery } from "@/api/task-run-concurrency-limits";
import { TaskRunConcurrencyLimitPage } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limit-page";

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
	component: RouteComponent,
	wrapInSuspense: true,
	loader: ({ context, params }) =>
		context.queryClient.ensureQueryData(
			buildConcurrenyLimitDetailsActiveRunsQuery(params.id),
		),
});

function RouteComponent() {
	const { id } = Route.useParams();
	return <TaskRunConcurrencyLimitPage id={id} />;
}
