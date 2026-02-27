import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { buildConcurrenyLimitDetailsActiveRunsQuery } from "@/api/task-run-concurrency-limits";
import { TaskRunConcurrencyLimitPage } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limit-page";
import { Skeleton } from "@/components/ui/skeleton";

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
	pendingComponent: function ConcurrencyLimitDetailSkeleton() {
		return (
			<div className="flex flex-col gap-4">
				<div className="flex items-center justify-between">
					<div className="flex items-center gap-2">
						<Skeleton className="h-6 w-40" />
						<Skeleton className="h-4 w-4" />
						<Skeleton className="h-6 w-32" />
					</div>
					<Skeleton className="h-8 w-8" />
				</div>
				<div className="grid gap-4" style={{ gridTemplateColumns: "3fr 1fr" }}>
					<div className="flex flex-col gap-3">
						<div className="flex gap-2 border-b">
							<Skeleton className="h-9 w-36" />
						</div>
						<Skeleton className="h-20 w-full" />
						<Skeleton className="h-20 w-full" />
						<Skeleton className="h-20 w-full" />
					</div>
					<div className="rounded-lg border p-4 flex flex-col gap-3">
						<Skeleton className="h-4 w-24" />
						<Skeleton className="h-4 w-32" />
						<Skeleton className="h-4 w-20" />
						<Skeleton className="h-4 w-28" />
					</div>
				</div>
			</div>
		);
	},
	loader: ({ context, params }) =>
		context.queryClient.ensureQueryData(
			buildConcurrenyLimitDetailsActiveRunsQuery(params.id),
		),
});
