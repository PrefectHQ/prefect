import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { categorizeError } from "@/api/error-utils";
import {
	buildCountGlobalConcurrencyLimitsQuery,
	buildGlobalConcurrencyLimitsPaginationBody,
	buildPaginateGlobalConcurrencyLimitsQuery,
} from "@/api/global-concurrency-limits";
import { buildListTaskRunConcurrencyLimitsQuery } from "@/api/task-run-concurrency-limits";
import { ConcurrencyLimitsPage } from "@/components/concurrency/concurrency-limits-page";
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";

/**
 * Schema for validating URL search parameters for the Concurrency Limits page.
 * @property {string} search used to filter data table
 * @property {'global' | 'task-run'} tab used designate which tab view to display
 * @property {number} page page of global concurrency limits to display. Must be positive. Defaults to 1.
 * @property {number} limit number of global concurrency limits to display per page. Must be positive.
 */
const searchParams = z.object({
	search: z.string().optional(),
	tab: z.enum(["global", "task-run"]).default("global"),
	page: z.number().int().positive().optional().default(1).catch(1),
	limit: z.number().int().positive().optional().catch(undefined),
});

export type TabOptions = z.infer<typeof searchParams>["tab"];

export const Route = createFileRoute("/concurrency-limits/")({
	validateSearch: searchParams,
	component: ConcurrencyLimitsPage,
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
	loaderDeps: ({ search }) =>
		buildGlobalConcurrencyLimitsPaginationBody({
			page: search.page,
			limit: search.limit,
			search: search.search,
		}),
	loader: ({ deps, context }) => {
		// Prefetch the page of global concurrency limits and its counts without
		// blocking the loader, so the search input stays interactive while results
		// update.
		void context.queryClient.prefetchQuery(
			buildPaginateGlobalConcurrencyLimitsQuery(deps),
		);
		void context.queryClient.prefetchQuery(
			buildCountGlobalConcurrencyLimitsQuery(),
		);
		void context.queryClient.prefetchQuery(
			buildCountGlobalConcurrencyLimitsQuery({
				concurrency_limits: deps.concurrency_limits,
			}),
		);

		return context.queryClient.ensureQueryData(
			buildListTaskRunConcurrencyLimitsQuery(),
		);
	},
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
