import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { categorizeError } from "@/api/error-utils";
import {
	buildCountGlobalConcurrencyLimitsQuery,
	buildGlobalConcurrencyLimitsCountFilter,
	buildGlobalConcurrencyLimitsFilter,
	buildListGlobalConcurrencyLimitsQuery,
} from "@/api/global-concurrency-limits";
import { buildListTaskRunConcurrencyLimitsQuery } from "@/api/task-run-concurrency-limits";
import { ConcurrencyLimitsPage } from "@/components/concurrency/concurrency-limits-page";
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";

/**
 * Schema for validating URL search parameters for the Concurrency Limits page.
 * @property {string} search used to filter data table
 * @property {'global' | 'task-run'} tab used designate which tab view to display
 * @property {number} offset used to paginate the global concurrency limits table
 * @property {number} limit used to paginate the global concurrency limits table
 */
const searchParams = z.object({
	search: z.string().optional(),
	tab: z.enum(["global", "task-run"]).default("global"),
	offset: z.number().int().nonnegative().optional().default(0).catch(0),
	limit: z.number().int().positive().optional().default(10).catch(10),
});

export type TabOptions = z.infer<typeof searchParams>["tab"];

export const Route = createFileRoute("/concurrency-limits/")({
	validateSearch: searchParams,
	component: ConcurrencyLimitsPage,
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
	loaderDeps: ({ search }) => search,
	loader: ({ deps, context }) =>
		Promise.all([
			context.queryClient.ensureQueryData(
				buildListGlobalConcurrencyLimitsQuery(
					buildGlobalConcurrencyLimitsFilter(deps),
				),
			),
			context.queryClient.ensureQueryData(
				buildCountGlobalConcurrencyLimitsQuery(
					buildGlobalConcurrencyLimitsCountFilter(deps),
				),
			),
			context.queryClient.ensureQueryData(
				buildCountGlobalConcurrencyLimitsQuery(),
			),
			context.queryClient.ensureQueryData(
				buildListTaskRunConcurrencyLimitsQuery(),
			),
		]),
	errorComponent: function ConcurrencyLimitsErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(
			error,
			"Failed to load concurrency limits",
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
					<h1 className="text-2xl font-semibold">Concurrency Limits</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
});
