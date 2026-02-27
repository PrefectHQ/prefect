import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { buildListGlobalConcurrencyLimitsQuery } from "@/api/global-concurrency-limits";
import { buildListTaskRunConcurrencyLimitsQuery } from "@/api/task-run-concurrency-limits";
import { ConcurrencyLimitsPage } from "@/components/concurrency/concurrency-limits-page";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Schema for validating URL search parameters for the Concurrency Limits page.
 * @property {string} search used to filter data table
 * @property {'global' | 'task-run'} tab used designate which tab view to display
 */
const searchParams = z.object({
	search: z.string().optional(),
	tab: z.enum(["global", "task-run"]).default("global"),
});

export type TabOptions = z.infer<typeof searchParams>["tab"];

/**
 * Skeleton component shown while the concurrency limits page is loading.
 * Displays placeholder elements for header, tab bar, and table rows.
 */
const concurrencyLimitsPageSkeleton = () => {
	return (
		<div className="flex flex-col gap-4">
			{/* Header skeleton */}
			<Skeleton className="h-8 w-44" />
			{/* Tab bar skeleton */}
			<div className="flex gap-2">
				<Skeleton className="h-9 w-28" />
				<Skeleton className="h-9 w-28" />
			</div>
			{/* Table skeleton */}
			<div className="rounded-md border">
				<div className="flex flex-col divide-y">
					{Array.from({ length: 8 }).map((_, i) => (
						<div
							key={`concurrency-skeleton-${String(i)}`}
							className="flex items-center gap-4 px-4 py-3"
						>
							<Skeleton className="h-4 w-40" />
							<Skeleton className="h-4 w-16 ml-auto" />
							<Skeleton className="h-4 w-20" />
						</div>
					))}
				</div>
			</div>
		</div>
	);
};

export const Route = createFileRoute("/concurrency-limits/")({
	validateSearch: zodValidator(searchParams),
	component: ConcurrencyLimitsPage,
	wrapInSuspense: true,
	pendingComponent: concurrencyLimitsPageSkeleton,
	loader: ({ context }) =>
		Promise.all([
			context.queryClient.ensureQueryData(
				buildListGlobalConcurrencyLimitsQuery(),
			),
			context.queryClient.ensureQueryData(
				buildListTaskRunConcurrencyLimitsQuery(),
			),
		]),
});
